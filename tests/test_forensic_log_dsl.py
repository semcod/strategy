from __future__ import annotations

from datetime import timezone, datetime, timedelta

from fastapi.testclient import TestClient

from planfile import Planfile, TicketSource
from planfile.api import server
from planfile.core.forensic_log_dsl import parse as parse_log
from planfile.core.forensic_log_dsl import serialize as serialize_log
from planfile.core.operational_dsl import line as operational_line
from planfile.core.operational_dsl import parse as parse_operational


def test_plog_is_compact_readable_and_round_trips() -> None:
    event = parse_operational(
        operational_line(
            timestamp="2026-08-05T12:00:00Z",
            kind="task",
            source="planfile.history",
            ticket_id="PLF-1",
            actor="bot:reviewer",
            oql="ticket.status_change",
            status="done",
            data={
                "payload": {
                    "reason": "Review passed",
                    "changes": ["status"],
                    "previous_status": "in_progress",
                    "status": "done",
                    "large_unneeded_result": "x" * 20_000,
                }
            },
        )
    )

    line = serialize_log(event)
    parsed = parse_log(line)

    assert line.startswith("PLOG/1\t")
    assert '"Review passed"' in line
    assert "large_unneeded_result" not in line
    assert len(line) < 1500
    assert parsed["ticket_id"] == "PLF-1"
    assert parsed["type"] == "ticket.status_change"
    assert parsed["logic"] == {
        "reason": "Review passed",
        "changes": ["status"],
        "previous_status": "in_progress",
        "status": "done",
    }


def test_ticket_lifecycle_and_evidence_are_written_to_public_log(tmp_path) -> None:
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Forensic lifecycle", source=TicketSource(tool="test"))
    pf.update_ticket(ticket.id, priority="high", actor="bot:test", reason="Triage decision")
    _, recorded = pf.append_ticket_evidence(
        ticket.id,
        idempotency_key="proof-1",
        collection="checks",
        evidence={"id": "proof-1", "passed": True},
        actor="bot:validator",
        reason="Independent check passed",
    )

    records = [parse_log(line) for line in pf.store.forensic_log_lines(ticket_id=ticket.id)]

    assert recorded is True
    assert [record["type"] for record in records] == [
        "ticket.create",
        "ticket.update",
        "ticket.evidence.append",
    ]
    assert records[1]["logic"]["reason"] == "Triage decision"
    assert records[2]["logic"] == {
        "reason": "Independent check passed",
        "collection": "checks",
        "idempotency_key": "proof-1",
    }
    assert pf.store._forensic_log_path.exists()


def test_historical_events_are_partitioned_by_utc_day(tmp_path) -> None:
    pf = Planfile(str(tmp_path))
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    with pf.store.mutation_lock():
        pf.store._append_operational_line(
            operational_line(
                timestamp=yesterday.isoformat(),
                ticket_id="PLF-OLD",
                actor="migration",
                oql="ticket.update",
                status="done",
                data={"payload": {"reason": "Historical migration"}},
            )
        )

    lines = pf.store.forensic_log_lines(
        date=yesterday.date().isoformat(),
        ticket_id="PLF-OLD",
    )

    assert len(lines) == 1
    assert parse_log(lines[0])["logic"]["reason"] == "Historical migration"
    assert (
        pf.store._forensic_log_history_dir
        / f"logs-{yesterday.date().isoformat()}.dsl.txt"
    ).exists()


def test_first_read_on_new_utc_day_rotates_the_public_file(tmp_path) -> None:
    pf = Planfile(str(tmp_path))
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    event = parse_operational(
        operational_line(
            timestamp=yesterday.isoformat(),
            ticket_id="PLF-YESTERDAY",
            actor="test",
            oql="ticket.update",
            data={"payload": {"reason": "Previous UTC day"}},
        )
    )
    pf.store._forensic_log_path.write_text(f"{serialize_log(event)}\n", encoding="utf-8")
    pf.store._forensic_log_date_path.write_text(
        f"{yesterday.date().isoformat()}\n", encoding="utf-8"
    )

    assert pf.store.forensic_log_lines() == []
    historical = pf.store.forensic_log_lines(date=yesterday.date().isoformat())

    assert len(historical) == 1
    assert parse_log(historical[0])["ticket_id"] == "PLF-YESTERDAY"


def test_existing_jsonl_is_backfilled_without_read_text(tmp_path, monkeypatch) -> None:
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Legacy operation", source=TicketSource(tool="test"))
    pf.store._forensic_log_path.unlink()
    pf.store._forensic_log_receipt_path.unlink()

    original_read_text = type(pf.store._operations_path).read_text

    def guarded_read_text(path, *args, **kwargs):
        if path == pf.store._operations_path:
            raise AssertionError("operations.jsonl must be streamed")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(type(pf.store._operations_path), "read_text", guarded_read_text)
    pf.store.ensure_forensic_log_projection()

    records = [parse_log(line) for line in pf.store.forensic_log_lines(ticket_id=ticket.id)]
    assert [record["type"] for record in records] == ["ticket.create"]
    assert pf.store.operational_events(ticket_id=ticket.id, limit=1)[0]["event"][
        "ticket_id"
    ] == ticket.id


def test_public_text_and_json_log_endpoints_and_management_ingest(tmp_path, monkeypatch) -> None:
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Public log", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    text_response = client.get(f"/logs.dsl.txt?ticket_id={ticket.id}&limit=10")
    json_response = client.get(f"/logs?ticket_id={ticket.id}&limit=10")
    ingested = client.post(
        "/events/ingest",
        json={
            "action": "review-decision",
            "ticket_id": ticket.id,
            "source": "validator-agent",
            "tool": "validator-agent",
            "status": "accepted",
            "message": "Autonomous review accepted the change.",
            "actor": "validator-agent[bot]",
            "correlation_id": "doctor-run-70",
            "causation_id": "repair-run-31011601205",
            "receipt_ref": "github-actions://31012632795",
            "reason": "Exact-head validation passed.",
            "decision": "approve",
            "outcome": "ready-to-merge",
            "error": "none",
            "idempotency_key": "validator-70-d4631e8",
        },
    )

    assert text_response.status_code == 200
    assert text_response.headers["x-planfile-log-format"] == "PLOG/1"
    assert text_response.text.startswith("PLOG/1\t")
    assert json_response.json()["events"][0]["type"] == "ticket.create"
    days = client.get("/logs/days").json()["days"]
    assert days[0]["file"] == "logs.dsl.txt"
    assert days[0]["bytes"] > 0
    assert ingested.status_code == 200
    durable = client.get(
        f"/logs?ticket_id={ticket.id}&event_type=event.review-decision"
    ).json()
    assert durable["count"] == 1
    assert durable["events"][0]["logic"]["message"] == (
        "Autonomous review accepted the change."
    )
    event = durable["events"][0]
    assert event["actor"] == "validator-agent[bot]"
    assert event["correlation_id"] == "doctor-run-70"
    assert event["causation_id"] == "repair-run-31011601205"
    assert event["receipt_ref"] == "github-actions://31012632795"
    assert event["logic"]["reason"] == "Exact-head validation passed."
    assert event["logic"]["decision"] == "approve"
    assert event["logic"]["outcome"] == "ready-to-merge"
    assert event["logic"]["error"] == "none"
    assert event["logic"]["idempotency_key"] == "validator-70-d4631e8"
