"""API/WebSocket tests for ticket execution events."""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient

from planfile import (
    Planfile,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
)
from planfile.api import server


def test_watcher_skips_full_ticket_projection_when_source_files_are_unchanged(monkeypatch):
    class StopWatch(Exception):
        pass

    snapshot_calls = 0
    sleep_calls = 0

    def snapshot():
        nonlocal snapshot_calls
        snapshot_calls += 1
        return (("same",), {"PLF-1": "state"}, {})

    async def sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise StopWatch

    monkeypatch.setattr(server, "_current_ticket_snapshot", snapshot)
    monkeypatch.setattr(server, "_ticket_snapshot_signature", lambda *_args: (("same",)))
    monkeypatch.setattr(server.asyncio, "sleep", sleep)

    with pytest.raises(StopWatch):
        asyncio.run(server._watch_planfile_changes(interval_seconds=0))

    assert snapshot_calls == 1


def test_websocket_broadcast_is_bounded_and_disconnects_stalled_clients(monkeypatch):
    delivered: list[dict] = []

    class StalledWebSocket:
        async def send_json(self, message):
            await asyncio.Event().wait()

    class HealthyWebSocket:
        async def send_json(self, message):
            delivered.append(message)

    stalled = StalledWebSocket()
    healthy = HealthyWebSocket()
    manager = server.ConnectionManager()
    manager.active.extend([stalled, healthy])

    real_wait_for = asyncio.wait_for

    async def fast_wait_for(awaitable, timeout):
        return await real_wait_for(awaitable, timeout=0.01)

    monkeypatch.setattr(server.asyncio, "wait_for", fast_wait_for)
    asyncio.run(manager.broadcast({"type": "ticket.changed"}))

    assert delivered == [{"type": "ticket.changed"}]
    assert manager.active == [healthy]


def _completion_receipt(ticket_id: str) -> dict:
    return {
        "schema": "subactor.completion-receipt.v1",
        "ticket_id": ticket_id,
        "outcome": "succeeded",
        "actor": "bot:test",
        "reason": "Expected state was observed.",
        "completed_at": "2026-07-20T21:00:00Z",
        "eql": [{"id": "expected-state", "passed": True, "expected": True, "actual": True}],
        "artifacts": ["audit:test"],
    }


def test_governed_ticket_requires_completion_receipt(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Governed process",
        labels=["process-envelope:v2"],
        execution=TicketExecution(state="running", last_error="stale_readiness_failure"),
        inputs=TicketInputs(
            process_manifest={
                "schema": "subactor.process-envelope.v2",
                "reason": "Governed test",
                "requested_by": "bot:test",
                "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [{}]},
            }
        ),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(f"/tickets/{ticket.id}/done").status_code == 409
    assert client.post(f"/tickets/{ticket.id}/complete", json={"result": {"ok": True}}).status_code == 409

    receipt = _completion_receipt(ticket.id)
    response = client.post(
        f"/tickets/{ticket.id}/complete",
        json={"note": "Verified", "result": {"ok": True}, "artifacts": ["audit:test"], "completion_receipt": receipt},
    )
    assert response.status_code == 200
    completed = response.json()
    assert completed["outputs"]["completion_receipt"] == receipt
    assert completed["execution"].get("last_error") is None
    assert completed["history"][-1]["actor"] == "bot:test"
    assert completed["history"][-1]["reason"] == "Expected state was observed."


@pytest.mark.parametrize("terminal_status", ["done", "canceled"])
def test_api_rejects_stale_worker_reopen_of_immutable_terminal(
    tmp_path,
    monkeypatch,
    terminal_status,
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Immutable API lifecycle",
        execution=TicketExecution(state="running", assigned_to="bot:worker"),
    )
    pf.update_ticket(ticket.id, status=terminal_status)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.patch(
        f"/tickets/{ticket.id}",
        json={
            "execution": {"state": "running", "assigned_to": "bot:late"},
            "actor": "bot:late",
            "reason": "stale_worker_update",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "immutable_terminal_reopen"}
    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.status == terminal_status
    assert current.execution.state == terminal_status


def test_governed_ticket_mutations_require_attributed_history(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    uri = {"id": "read-time", "name": "Read time", "uri": "time://clock/query/now"}
    ticket = pf.create_ticket(
        name="Governed history",
        labels=["process-envelope:v2"],
        execution=TicketExecution(state="running", max_attempts=2),
        inputs=TicketInputs(
            uri_processes=[uri],
            process_manifest={
                "schema": "subactor.process-envelope.v2",
                "reason": "Governed history test",
                "requested_by": "bot:test",
                "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [uri]},
            },
        ),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.patch(f"/tickets/{ticket.id}", json={"priority": "high"}).status_code == 422
    assert client.post(f"/tickets/{ticket.id}/fail", json={"error": "temporary"}).status_code == 422
    updated = client.patch(
        f"/tickets/{ticket.id}",
        json={"priority": "high", "actor": "bot:test", "reason": "Escalated priority after preflight."},
    )
    assert updated.status_code == 200
    assert updated.json()["history"][-1]["actor"] == "bot:test"
    assert updated.json()["history"][-1]["reason"] == "Escalated priority after preflight."


def test_fail_api_returns_conflict_for_stale_updated_at_precondition(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Watchdog candidate",
        execution=TicketExecution(state="running", assigned_to="bot:worker", max_attempts=2),
    )
    observed_updated_at = ticket.model_dump(mode="json")["updated_at"]
    changed = pf.update_ticket(ticket.id, priority="high")
    assert changed is not None
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    conflict = client.post(
        f"/tickets/{ticket.id}/fail-if-current",
        json={
            "error": "stale_execution_timeout",
            "expected_updated_at": observed_updated_at,
        },
    )

    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "ticket_updated_at_precondition_failed"}
    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.priority == "high"
    assert current.execution.state == "running"
    assert current.execution.attempt == 0


def test_fail_api_accepts_current_updated_at_in_json_timestamp_form(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Current watchdog candidate",
        execution=TicketExecution(state="running", assigned_to="bot:worker", max_attempts=2),
    )
    expected_updated_at = ticket.model_dump(mode="json")["updated_at"]
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post(
        f"/tickets/{ticket.id}/fail",
        json={
            "error": "stale_execution_timeout",
            "expected_updated_at": expected_updated_at,
        },
    )

    assert response.status_code == 200
    assert response.json()["execution"]["state"] == "ready"
    assert response.json()["execution"]["attempt"] == 1


def test_fail_if_current_api_requires_updated_at_precondition(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Fail-closed watchdog candidate",
        execution=TicketExecution(state="running", assigned_to="bot:worker"),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post(
        f"/tickets/{ticket.id}/fail-if-current",
        json={"error": "stale_execution_timeout"},
    )

    assert response.status_code == 422
    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.status == "open"
    assert current.execution is not None
    assert current.execution.attempt == 0


def test_governed_ticket_creation_requires_structured_four_part_envelope(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    invalid = client.post(
        "/tickets",
        json={
            "name": "Incomplete governed process",
            "labels": ["process-envelope:v2"],
            "inputs": {
                "process_manifest": {
                    "schema": "subactor.process-envelope.v2",
                    "reason": "test",
                    "requested_by": "bot:test",
                    "definitions": {"aql": [{}], "eql": [], "oql": [{}], "uri": [{}]},
                }
            },
        },
    )
    assert invalid.status_code == 422
    assert "process_definitions_incomplete:eql" in invalid.json()["detail"]

    uri = {"id": "read-time", "name": "Read time", "uri": "time://clock/query/now"}
    valid = client.post(
        "/tickets",
        json={
            "name": "Complete governed process",
            "labels": ["process-envelope:v2"],
            "inputs": {
                "uri_processes": [uri],
                "process_manifest": {
                    "schema": "subactor.process-envelope.v2",
                    "reason": "test",
                    "requested_by": "bot:test",
                    "definitions": {"aql": [{}], "eql": [{}], "oql": [{}], "uri": [uri]},
                },
            },
        },
    )
    assert valid.status_code == 201


def test_production_gate_rejects_every_legacy_ticket_creation(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "1")
    client = TestClient(server.app)

    response = client.post("/tickets", json={"name": "Legacy ticket"})

    assert response.status_code == 422
    assert response.json()["detail"] == "process_envelope_required"


def test_production_gate_does_not_freeze_existing_legacy_ticket(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Existing legacy ticket")
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    monkeypatch.setenv("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "1")
    client = TestClient(server.app)

    response = client.patch(
        f"/tickets/{ticket.id}",
        json={
            "status": "failed",
            "actor": "automation:legacy-migration",
            "reason": "Normalize an exhausted legacy execution.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["execution"]["state"] == "failed"


def test_lifecycle_api_broadcasts_ticket_execution_event(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Run bootstrap shell",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic"),
        execution=TicketExecution(state="pending"),
    )

    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            f"/tickets/{ticket.id}/claim",
            json={"assigned_to": "koru-shell", "lease_seconds": 60},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    assert event["type"] == "ticket.execution.changed"
    assert event["action"] == "claim"
    assert event["ticket_id"] == ticket.id
    assert event["ticket"]["execution"]["state"] == "ready"
    assert event["ticket"]["execution"]["assigned_to"] == "koru-shell"


def test_ticket_update_api_broadcasts_ticket_changed_event(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Document bootstrap flow",
        source=TicketSource(tool="human"),
    )

    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.patch(
            f"/tickets/{ticket.id}",
            json={"priority": "high"},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    assert event["type"] == "ticket.changed"
    assert event["action"] == "update"
    assert event["ticket_id"] == ticket.id
    assert event["ticket"]["priority"] == "high"


def test_ticket_lifecycle_api_persists_history_for_detail_panel(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Needs durable history",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="pending"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(
        f"/tickets/{ticket.id}/claim",
        json={"assigned_to": "koru-shell"},
    ).status_code == 200
    assert client.post(
        f"/tickets/{ticket.id}/input-required",
        json={"prompt": "Provide API key", "env_keys": ["OPENROUTER_API_KEY"]},
    ).status_code == 200

    loaded = client.get(f"/tickets/{ticket.id}").json()

    assert [entry["action"] for entry in loaded["history"]] == ["update", "update"]
    assert loaded["history"][0]["changes"] == ["execution"]
    assert loaded["history"][0]["execution_state"] == "ready"
    assert loaded["history"][1]["execution_state"] == "waiting_input"
    assert loaded["history"][1]["previous_execution_state"] == "ready"


def test_ticket_response_api_defaults_to_ready_and_broadcasts(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Human response",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="waiting_input"),
    )
    server._manager.active.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True
        response = client.post(
            f"/tickets/{ticket.id}/respond",
            json={"note": "Proceed with the requested access.", "actor": "founder"},
        )
        event = ws.receive_json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "open"
    assert payload["execution"]["state"] == "ready"
    assert payload["outputs"]["notes"] == ["Proceed with the requested access."]
    assert event["action"] == "respond"
    assert event["ticket"]["execution"]["state"] == "ready"


def test_ticket_response_api_null_state_preserves_current_status(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Add context without changing status",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="running", assigned_to="founder"),
        status="in_progress",
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.post(
        f"/tickets/{ticket.id}/respond",
        json={"note": "Additional context only.", "next_state": None, "actor": "founder"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["execution"]["state"] == "running"
    assert payload["execution"]["assigned_to"] == "founder"
    assert payload["outputs"]["notes"] == ["Additional context only."]


def test_root_serves_queue_dashboard(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(
        name="Dashboard visible ticket",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert "planfile queue dashboard" in response.text
    assert "Notification.requestPermission" in response.text
    assert "new WebSocket" in response.text
    assert "queue-filter" in response.text
    assert "status-filter" in response.text
    assert "Test notification" in response.text
    assert "setInterval" in response.text
    assert "scheduleTicketRefresh" in response.text
    assert 'fetch("/tickets?limit=1000&view=summary"' in response.text
    assert "let ticketRefreshPromise = null" in response.text
    assert "ticketRefreshQueued = true" in response.text
    assert "}, 60000);" in response.text
    assert "loadEventHistory" in response.text
    assert "applyUrlState" in response.text
    assert "syncUrlState" in response.text
    assert 'params.set("ticket", state.selectedTicketId)' in response.text
    assert 'params.set("queue", state.queue)' in response.text
    assert 'params.set("status", state.statusFilter)' in response.text
    assert 'params.set("tab", state.detailTab)' in response.text
    assert "Copy JSON to clipboard" in response.text
    assert "function installCopyControls" in response.text
    assert 'pre:not([data-copy-enhanced])' in response.text
    assert "copy-inline-control" in response.text
    assert "Manage actor permissions" in response.text
    assert "Delegation manager" in response.text
    assert 'href="${escapeHtml(accessHref)}"' in response.text
    assert "Respond to this ticket" in response.text
    assert "data-ticket-response-form" in response.text
    assert "Delegate to actor / queue" in response.text
    assert 'name="delegate_to"' in response.text
    assert '<select id="ticket-delegate-to" name="delegate_to"' in response.text
    assert 'name="delegate_kind"' not in response.text
    assert 'fetch("/delegation/actors"' in response.text
    assert "URI Process plan" in response.text
    assert '<option value="" selected>Keep current status</option>' in response.text
    assert '<option value="ready">READY' in response.text
    assert 'value="in_progress"' in response.text
    assert "/respond" in response.text
    assert "beginTicketWork" not in response.text
    assert "data-start-ticket" in response.text
    assert "async function startSelectedTicket" in response.text
    assert "/start" in response.text
    assert ".slice(0, 80)" not in response.text
    assert "tickets-count" in response.text
    assert "copyTicketDetailJson" in response.text
    assert "ticketDetailExportPayload" in response.text
    assert "/events?limit=100" in response.text
    assert "Ticket Detail" in response.text
    assert "ticket-detail" in response.text
    assert "data-detail-tab" in response.text
    assert "Tool logs" in response.text
    assert "Raw JSON" in response.text
    assert "data-ticket-id" in response.text
    assert "function selectTicket(ticketId" in response.text
    assert "/events?ticket_id=" in response.text
    assert "renderTicketTimeline" in response.text
    assert "Related tickets and splits" in response.text
    assert '{ cache: "no-store" }' in response.text
    assert "scanTicketStatuses" in response.text
    assert "Ticket status changes and errors" in response.text
    assert "management.event" in response.text
    assert "if (event?.queue) return String(event.queue);" in response.text
    assert "function isRunningTicket(ticket)" in response.text
    assert "function ticketMatchesStatus(ticket)" in response.text
    assert 'localStorage.setItem("planfile.statusFilter", state.statusFilter)' in response.text
    assert 'ticket?.status === "in_progress"' in response.text
    assert "if (isWaitingTicket(ticket) || isFailedTicket(ticket) || stateName === \"done\") return false;" in response.text
    assert "const running = visibleTickets.filter(isRunningTicket).length;" in response.text
    assert "/runtime-context" in response.text


def test_access_panel_redirects_to_configured_aql_actor_editor(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_ACCESS_PANEL_URL", "https://control.example.test/panel?source=planfile")
    catalogue = tmp_path / "actors.json"
    catalogue.write_text(
        json.dumps({"actors": [{"id": "administrator-bot", "label": "Administrator", "kind": "bot"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLANFILE_DELEGATION_ACTORS_FILE", str(catalogue))
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/access-panel?actor=administrator-bot", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == (
        "https://control.example.test/panel?source=planfile&tab=access&action=edit&actor=administrator-bot"
    )
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert client.get("/access-panel?actor=unknown", follow_redirects=False).status_code == 422
    manager = client.get("/access-panel?view=delegation", follow_redirects=False)
    assert manager.status_code == 307
    assert "tab=delegation&action=view" in manager.headers["location"]


def test_delegation_actor_catalog_api_and_validation(tmp_path, monkeypatch):
    catalogue = tmp_path / "delegation-actors.json"
    catalogue.write_text(json.dumps({"actors": [
        {"id": "founder", "label": "Founder", "kind": "human"},
        {"id": "project-operator-bot", "label": "Project operator", "kind": "bot"},
    ]}))
    monkeypatch.setenv("PLANFILE_DELEGATION_ACTORS_FILE", str(catalogue))
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Delegate through API", source=TicketSource(tool="human"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    actors = client.get("/delegation/actors")
    assert actors.status_code == 200
    assert [actor["id"] for actor in actors.json()] == ["founder", "project-operator-bot"]

    rejected = client.post(f"/tickets/{ticket.id}/respond", json={
        "note": "Invalid delegation", "delegate_to": "invented-person",
    })
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "ticket_delegate_not_allowed:invented-person"

    delegated = client.post(f"/tickets/{ticket.id}/respond", json={
        "note": "Run the project", "delegate_to": "project-operator-bot",
    })
    assert delegated.status_code == 200
    assert delegated.json()["executor"] == {
        "kind": "bot", "mode": "automatic", "handler": "project-operator-bot"
    }


def test_runtime_context_api_and_page(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    page = client.get("/runtime-context")
    assert page.status_code == 200
    assert "Topology / Runtime Context" in page.text
    assert "/api/runtime-context" in page.text
    assert "function installCopyBlocks" in page.text
    assert "copyable-code" in page.text

    response = client.get("/api/runtime-context")
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_root"] == str(tmp_path.resolve())
    assert payload["summary"]["project"] == tmp_path.name
    assert payload["config"]["enabled"]["systems"] is True

    update = client.put(
        "/api/runtime-context/config",
        json={"enabled": {"systems": False, "pipelines": True}, "overrides": {"note": "test"}},
    )
    assert update.status_code == 200
    saved = update.json()
    assert saved["enabled"]["systems"] is False
    assert saved["enabled"]["pipelines"] is True
    assert saved["overrides"]["note"] == "test"

    refreshed = client.get("/api/runtime-context").json()
    assert refreshed["config"]["enabled"]["systems"] is False
    assert refreshed["systems"] == []


def test_runtime_context_get_does_not_create_config(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    config_path = tmp_path / ".koru" / "runtime-context.json"
    assert client.get("/api/runtime-context/config").status_code == 200
    assert not config_path.exists()


def test_runtime_context_discovers_monorepo_and_redacts_compose_environment(tmp_path, monkeypatch):
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "package.json").write_text(
        json.dumps({"name": "child-service", "version": "1.2.3"}),
        encoding="utf-8",
    )
    (tmp_path / "platform").mkdir()
    (tmp_path / "platform" / "docker-compose.yml").write_text(
        "services:\n  api:\n    environment:\n      API_TOKEN: super-secret\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PLANFILE_RUNTIME_CONTEXT_PROJECT_NAME", "example-monorepo")

    context = server.build_runtime_context(tmp_path)

    assert context["summary"]["project"] == "example-monorepo"
    assert context["summary"]["workspaces"] == 1
    assert context["systems"][0]["compose_files"] == ["platform/docker-compose.yml"]
    assert context["systems"][0]["environment"] == {"API_TOKEN": "<redacted>"}


def test_openapi_and_health_publish_same_version():
    client = TestClient(server.app)

    assert client.get("/openapi.json").json()["info"]["version"] == client.get("/health").json()["version"]
    assert "ticket.fail.expected_updated_at" in client.get("/health").json()["capabilities"]


def test_ticket_list_pagination_headers(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    for index in range(3):
        pf.create_ticket(name=f"Ticket {index}", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets?sprint=all&view=full&offset=1&limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.headers["x-total-count"] == "3"
    assert response.headers["x-result-count"] == "1"
    assert response.headers["x-planfile-view"] == "full"


def test_ticket_list_operational_view_keeps_execution_contract_without_unbounded_journal(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Operational projection",
        description="The controller may still need a legacy fallback description.",
        labels=["process-envelope:v2"],
        source=TicketSource(tool="test", context={"large": "context"}),
        executor=TicketExecutor(kind="api", mode="automatic", handler="uri-process"),
        execution=TicketExecution(queue="project-bot", state="ready"),
        inputs=TicketInputs(
            prompt="Execute",
            uri_processes=[
                {
                    "id": "inspect",
                    "name": "Inspect",
                    "uri": "test://resource/command/inspect",
                }
            ],
            process_manifest={
                "schema": server.PROCESS_ENVELOPE_SCHEMA,
                "reason": "test",
                "requested_by": "human:test",
                "definitions": {
                    "aql": [{"id": "aql:test"}],
                    "eql": [{"id": "eql:test"}],
                    "oql": [{"id": "oql:test"}],
                    "uri": [{"id": "inspect", "uri": "test://resource/command/inspect"}],
                },
            },
        ),
        outputs=TicketOutputs(
            artifacts=["artifact://large"],
            notes=["large journal entry"],
            result={"blocker": "waiting_for_input"},
            completion_receipt={"schema": server.COMPLETION_RECEIPT_SCHEMA},
        ),
    )
    pf.update_ticket(
        ticket.id,
        status="in_progress",
        actor="test",
        reason="create history",
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets?sprint=all&view=operational")

    assert response.status_code == 200
    assert response.headers["x-planfile-view"] == "operational"
    payload = response.json()[0]
    assert payload["id"] == ticket.id
    assert payload["description"].startswith("The controller")
    assert payload["executor"]["handler"] == "uri-process"
    assert payload["execution"]["queue"] == "project-bot"
    assert payload["inputs"]["process_manifest"]["schema"] == server.PROCESS_ENVELOPE_SCHEMA
    assert payload["inputs"]["uri_processes"][0]["uri"] == "test://resource/command/inspect"
    assert payload["outputs"]["result"] == {"blocker": "waiting_for_input"}
    assert payload["outputs"]["completion_receipt"]["schema"] == server.COMPLETION_RECEIPT_SCHEMA
    assert "notes" not in payload["outputs"]
    assert "artifacts" not in payload["outputs"]
    assert "history" not in payload
    assert "dsl" not in payload
    assert "context" not in payload["source"]

    full = client.get("/tickets?sprint=all&view=full").json()[0]
    assert full["outputs"]["notes"] == ["large journal entry"]
    assert full["outputs"]["artifacts"] == ["artifact://large"]
    assert full["history"]


def test_ticket_summary_view_keeps_queue_fields_and_omits_execution_contract(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Queue summary",
        description="Large detail loaded only after selection.",
        labels=["queue"],
        source=TicketSource(tool="test", context={"large": "context"}),
        executor=TicketExecutor(kind="api", mode="automatic", handler="worker"),
        execution=TicketExecution(queue="project-bot", state="ready"),
        inputs=TicketInputs(prompt="Large governed input"),
        outputs=TicketOutputs(result={"large": "result"}, notes=["journal"]),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets?view=summary")

    assert response.status_code == 200
    assert response.headers["x-planfile-view"] == "summary"
    payload = response.json()[0]
    assert payload["id"] == ticket.id
    assert payload["name"] == "Queue summary"
    assert payload["labels"] == ["queue"]
    assert payload["executor"]["handler"] == "worker"
    assert payload["execution"]["queue"] == "project-bot"
    assert "description" not in payload
    assert "source" not in payload
    assert "inputs" not in payload
    assert "outputs" not in payload
    assert "history" not in payload


def test_all_without_explicit_view_gets_bounded_current_summary(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    current = pf.create_ticket(
        name="Browser queue",
        description="Must not be copied into every dashboard refresh.",
        source=TicketSource(tool="test"),
    )
    pf.create_ticket(
        name="Archived ticket",
        sprint="archive",
        source=TicketSource(tool="test"),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get(
        "/tickets?sprint=all",
        headers={"user-agent": "Mozilla/5.0"},
    )

    assert response.status_code == 200
    assert response.headers["x-planfile-view"] == "summary"
    assert [ticket["id"] for ticket in response.json()] == [current.id]
    assert "description" not in response.json()[0]

    explicit_archive = client.get(
        "/tickets?sprint=all&view=summary",
        headers={"user-agent": "Mozilla/5.0"},
    )
    assert {ticket["name"] for ticket in explicit_archive.json()} == {
        "Browser queue",
        "Archived ticket",
    }

    service_client = client.get(
        "/tickets?sprint=all",
        headers={"user-agent": "undici"},
    )
    assert service_client.headers["x-planfile-view"] == "summary"
    assert [ticket["id"] for ticket in service_client.json()] == [current.id]


def test_move_ticket_api_and_sprint_validation(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Move through API", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    moved = client.post(f"/tickets/{ticket.id}/move?to_sprint=audit-sprint")

    assert moved.status_code == 200
    assert pf.get_ticket(ticket.id).sprint == "audit-sprint"
    assert client.post(f"/tickets/{ticket.id}/move?to_sprint=../../escape").status_code == 422
    assert client.post(
        "/tickets",
        json={"name": "Escape", "sprint": "../../escape"},
    ).status_code == 422


def test_sprint_api_uses_canonical_sprint_store(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Current work", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    listed = client.get("/sprints")
    created = client.post(
        "/sprints",
        json={"id": "release-1", "name": "Release 1", "objectives": ["Ship"]},
    )

    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {"backlog", "current"}
    assert next(item for item in listed.json() if item["id"] == "current")["ticket_count"] == 1
    assert created.status_code == 201
    assert created.json()["id"] == "release-1"
    assert client.post(
        "/sprints",
        json={"id": "release-1", "name": "Duplicate"},
    ).status_code == 409
    assert {item["id"] for item in client.get("/sprints").json()} == {
        "backlog", "current", "release-1"
    }


def test_sprint_summary_cache_reparses_only_the_changed_sprint(tmp_path, monkeypatch):
    from planfile.core import fastio

    pf = Planfile(str(tmp_path))
    pf.create_ticket(name="Initial", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._SPRINT_SUMMARY_CACHE.clear()
    reads: list[str] = []
    original = fastio.read_yaml_fast

    def counted(path):
        reads.append(str(path))
        return original(path)

    monkeypatch.setattr(fastio, "read_yaml_fast", counted)
    client = TestClient(server.app)

    assert client.get("/sprints").status_code == 200
    initial_reads = len(reads)
    assert initial_reads == 2
    assert client.get("/sprints").status_code == 200
    assert len(reads) == initial_reads

    pf.create_ticket(name="Changed current", source=TicketSource(tool="test"))
    reads_before_refresh = len(reads)
    listed = client.get("/sprints")

    assert listed.status_code == 200
    assert len(reads) == reads_before_refresh + 1
    assert next(item for item in listed.json() if item["id"] == "current")["ticket_count"] == 2


def test_favicon_returns_no_content():
    client = TestClient(server.app)
    response = client.get("/favicon.ico")

    assert response.status_code == 204


def test_next_ticket_api_filters_by_queue(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    pf.create_ticket(
        name="Default queue",
        priority="critical",
        execution=TicketExecution(queue="default", state="ready"),
    )
    refactor = pf.create_ticket(
        name="Refactor queue",
        priority="high",
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    response = client.get("/tickets/next?queue=c2004-refactor")

    assert response.status_code == 200
    assert response.json()["id"] == refactor.id


def test_events_api_returns_recent_events_and_filters_by_queue(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    default_ticket = pf.create_ticket(
        name="Default event",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="pending"),
    )
    refactor_ticket = pf.create_ticket(
        name="Refactor event",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="c2004-refactor", state="pending"),
    )

    server._manager.active.clear()
    server._event_history.clear()
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.post(f"/tickets/{default_ticket.id}/ready").status_code == 200
    assert client.post(f"/tickets/{refactor_ticket.id}/ready").status_code == 200

    all_response = client.get("/events")
    refactor_response = client.get("/events?queue=c2004-refactor")
    all_events = all_response.json()
    refactor_events = refactor_response.json()

    assert all_response.headers["cache-control"] == "no-store, max-age=0"
    assert refactor_response.headers["cache-control"] == "no-store, max-age=0"
    assert [event["ticket_id"] for event in all_events][-2:] == [
        default_ticket.id,
        refactor_ticket.id,
    ]
    assert [event["ticket_id"] for event in refactor_events] == [refactor_ticket.id]
    assert "created_at" in refactor_events[0]


def test_test_event_api_broadcasts_and_records_synthetic_error():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            "/events/test",
            json={"queue": "c2004-runtime", "message": "Synthetic failure"},
        )

        assert response.status_code == 200
        event = ws.receive_json()

    history = client.get("/events?queue=c2004-runtime").json()

    assert event["type"] == "dashboard.test"
    assert event["ticket_id"] == "TEST"
    assert event["ticket"]["execution"]["state"] == "failed"
    assert event["ticket"]["execution"]["last_error"] == "Synthetic failure"
    assert history[-1]["type"] == "dashboard.test"


def test_management_event_api_broadcasts_records_and_filters_by_queue():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["ok"] is True

        response = client.post(
            "/events/ingest",
            json={
                "source": "koru",
                "tool": "koru.queue",
                "action": "completed",
                "ticket_id": "PLF-074",
                "status": "completed",
                "level": "info",
                "queue": "c2004-runtime",
                "message": "Executed PLF-074",
                "details": {"executor": "shell"},
            },
        )

        assert response.status_code == 200
        event = ws.receive_json()

    runtime_events = client.get("/events?queue=c2004-runtime").json()
    default_events = client.get("/events?queue=default").json()

    assert event["type"] == "management.event"
    assert event["tool"] == "koru.queue"
    assert event["action"] == "completed"
    assert event["queue"] == "c2004-runtime"
    assert event["ticket_id"] == "PLF-074"
    assert event["details"]["ticket_id"] == "PLF-074"
    assert runtime_events[-1]["type"] == "management.event"
    assert default_events == []


def test_events_api_filters_management_events_by_ticket_id():
    server._manager.active.clear()
    server._event_history.clear()

    client = TestClient(server.app)

    assert client.post(
        "/events/ingest",
        json={
            "source": "koru",
            "tool": "koru.shell",
            "action": "step-log",
            "status": "warning",
            "level": "warning",
            "queue": "c2004-refactor",
            "message": "human input required before continuing",
            "details": {"ticket_id": "PLF-070", "split_ticket_id": "PLF-077"},
        },
    ).status_code == 200
    assert client.post(
        "/events/ingest",
        json={
            "source": "koru",
            "tool": "koru.shell",
            "action": "step-log",
            "status": "info",
            "level": "info",
            "queue": "c2004-runtime",
            "message": "unrelated",
            "details": {"ticket_id": "PLF-074"},
        },
    ).status_code == 200

    response = client.get("/events?ticket_id=PLF-070")
    events = response.json()

    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert len(events) == 1
    assert events[0]["ticket_id"] == "PLF-070"
    assert events[0]["details"]["split_ticket_id"] == "PLF-077"
    assert client.get("/events?ticket_id=PLF-999").json() == []


def test_tickets_api_reads_updated_store_and_disables_cache(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Status changes outside dashboard",
        source=TicketSource(tool="human"),
        execution=TicketExecution(queue="default", state="ready"),
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    first = client.get("/tickets?sprint=all&view=full")
    pf.complete_ticket(ticket.id, note="done outside API")
    second = client.get("/tickets?sprint=all&view=full")

    assert first.headers["cache-control"] == "no-store, max-age=0"
    assert second.headers["cache-control"] == "no-store, max-age=0"
    assert next(item for item in first.json() if item["id"] == ticket.id)["status"] == "open"
    assert next(item for item in second.json() if item["id"] == ticket.id)["status"] == "done"


def test_tickets_api_reuses_serialized_unchanged_snapshot(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Cached list", source=TicketSource(tool="test"))
    calls = 0
    original = pf.list_tickets

    def counted(**filters):
        nonlocal calls
        calls += 1
        return original(**filters)

    monkeypatch.setattr(pf, "list_tickets", counted)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.get("/tickets?sprint=all").status_code == 200
    assert client.get("/tickets?sprint=all").status_code == 200
    assert calls == 1

    pf.update_ticket(ticket.id, name="Changed snapshot")

    assert client.get("/tickets?sprint=all").json()[0]["name"] == "Changed snapshot"
    assert calls == 2


def test_ticket_list_cache_evicts_superseded_versions_of_the_same_query(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Cache version 0", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    path = "/tickets?sprint=all&limit=5000&view=full"

    for version in range(6):
        if version:
            pf.update_ticket(ticket.id, name=f"Cache version {version}")
        assert client.get(path).status_code == 200

    project_keys = [
        key
        for key in server._TICKET_LIST_RESPONSE_CACHE
        if key[0] == str(pf.store.project_dir)
    ]
    assert len(project_keys) == 1
    assert client.get(path).json()[0]["name"] == "Cache version 5"


def test_ticket_list_cache_does_not_retain_response_larger_than_byte_budget(
    monkeypatch,
):
    monkeypatch.setenv("PLANFILE_TICKET_RESPONSE_CACHE_MAX_BYTES", str(1024 * 1024))
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    query_key = ("/project", "all", (), 0, 5000, "full")
    versioned_key = query_key + ((1, 1),)

    server._cache_ticket_list_response(
        query_key=query_key,
        versioned_key=versioned_key,
        body=b"x" * (1024 * 1024 + 1),
        total=1,
        count=1,
    )

    assert server._TICKET_LIST_RESPONSE_CACHE == {}
    assert server._TICKET_LIST_LATEST == {}
    assert server._ticket_list_response_cached_bytes() == 0


def test_ticket_list_cache_default_budget_shares_one_large_archive(monkeypatch):
    monkeypatch.delenv("PLANFILE_TICKET_RESPONSE_CACHE_MAX_BYTES", raising=False)

    assert server._ticket_list_response_cache_byte_limit() == 256 * 1024 * 1024


def test_ticket_list_cache_evicts_other_queries_before_exceeding_byte_budget(
    monkeypatch,
):
    monkeypatch.setenv("PLANFILE_TICKET_RESPONSE_CACHE_MAX_BYTES", str(1024 * 1024))
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    first_query = ("/project", "all", (), 0, 5000, "full")
    second_query = ("/project", "current", (), 0, 1000, "operational")
    first_body = b"a" * (700 * 1024)
    second_body = b"b" * (700 * 1024)

    server._cache_ticket_list_response(
        query_key=first_query,
        versioned_key=first_query + ((1, 1),),
        body=first_body,
        total=1,
        count=1,
    )
    server._cache_ticket_list_response(
        query_key=second_query,
        versioned_key=second_query + ((1, 2),),
        body=second_body,
        total=1,
        count=1,
    )

    assert first_query not in server._TICKET_LIST_LATEST
    assert second_query in server._TICKET_LIST_LATEST
    assert server._ticket_list_response_cached_bytes() == len(second_body)
    assert server._ticket_list_response_cached_bytes() <= 1024 * 1024


def test_dashboard_gets_bounded_stale_snapshot_during_mutation_burst(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Before burst", source=TicketSource(tool="test"))
    now = 100.0
    monkeypatch.setattr(server.time, "monotonic", lambda: now)
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    headers = {"user-agent": "Mozilla/5.0"}

    assert client.get("/tickets?sprint=all", headers=headers).json()[0]["name"] == "Before burst"
    pf.update_ticket(ticket.id, name="During burst")
    assert client.get("/tickets?sprint=all", headers=headers).json()[0]["name"] == "Before burst"

    now += server._DASHBOARD_STALE_WINDOW_SECONDS + 0.1

    assert client.get("/tickets?sprint=all", headers=headers).json()[0]["name"] == "During burst"


def test_post_tickets_creates_ticket_via_json_api(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    response = client.post(
        "/tickets",
        json={
            "name": "Created from REST",
            "description": "via dashboard API",
            "priority": "high",
            "sprint": "current",
            "labels": ["dashboard", "api"],
            "executor": {"kind": "human", "mode": "interactive"},
            "execution": {"queue": "default", "state": "ready"},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Created from REST"
    assert data["id"]
    assert data["execution"]["queue"] == "default"
    assert data["executor"]["kind"] == "human"

    listed = client.get("/tickets?sprint=all").json()
    assert any(t["id"] == data["id"] for t in listed)


def test_evidence_api_atomically_appends_and_deduplicates_external_receipt(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="External effect", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    payload = {
        "idempotency_key": "execution:send-123",
        "collection": "process_executions",
        "evidence": {
            "schema": "subactor.process-result.v1",
            "execution_id": "execution:send-123",
            "status": "succeeded",
        },
        "notes": ["SUBACTOR_PROCESS_RESULT_V1 send-123"],
        "artifacts": ["bridge-audit.jsonl#execution_id=send-123"],
        "actor": "hr-bridge",
        "reason": "Persist SMTP delivery evidence.",
    }

    sprint_file = pf.store._sprint_file("current")
    sprint_mtime = sprint_file.stat().st_mtime_ns
    first = client.post(f"/tickets/{ticket.id}/evidence", json=payload)
    second = client.post(f"/tickets/{ticket.id}/evidence", json=payload)

    assert first.status_code == 200
    assert first.json()["recorded"] is True
    assert first.json()["deduplicated"] is False
    assert second.status_code == 200
    assert second.json()["recorded"] is False
    assert second.json()["deduplicated"] is True

    updated = pf.get_ticket(ticket.id)
    assert updated is not None
    assert updated.outputs.notes == ["SUBACTOR_PROCESS_RESULT_V1 send-123"]
    assert updated.outputs.artifacts == ["bridge-audit.jsonl#execution_id=send-123"]
    executions = updated.outputs.result["process_executions"]
    assert len(executions) == 1
    assert executions[0]["execution_id"] == "execution:send-123"
    assert executions[0]["idempotency_key"] == "execution:send-123"
    assert sprint_file.stat().st_mtime_ns == sprint_mtime
    assert pf.store._ticket_evidence_path(ticket.id).exists()

    # The append-only journal is durable source data, not an in-process cache.
    reopened = Planfile(str(tmp_path)).get_ticket(ticket.id)
    assert reopened.outputs.result["process_executions"][0]["execution_id"] == "execution:send-123"


def test_evidence_append_invalidates_the_serialized_ticket_list_projection(
    tmp_path, monkeypatch
):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="List projection", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    assert client.get("/tickets?sprint=all&view=full").json()[0].get("outputs") is None
    response = client.post(
        f"/tickets/{ticket.id}/evidence",
        json={
            "idempotency_key": "projection-1",
            "collection": "process_executions",
            "evidence": {"execution_id": "projection-1", "status": "succeeded"},
            "actor": "hr-bridge",
            "reason": "Persist projected receipt.",
        },
    )

    assert response.status_code == 200
    listed = client.get("/tickets?sprint=all&view=full").json()[0]
    assert listed["outputs"]["result"]["process_executions"][0]["execution_id"] == "projection-1"


def test_evidence_append_does_not_invalidate_unrelated_sprint_models(tmp_path):
    pf = Planfile(str(tmp_path))
    active = pf.create_ticket(name="Active evidence", source=TicketSource(tool="test"))
    pf.create_ticket(
        name="Archived model",
        sprint="archive-test",
        source=TicketSource(tool="test"),
    )
    pf.list_tickets(sprint="all")
    archive_key = str(pf.store._sprint_file("archive-test"))
    current_key = str(pf.store._sprint_file("current"))
    archive_before = pf.store._ticket_model_cache[archive_key]
    current_before = pf.store._ticket_model_cache[current_key]

    pf.append_ticket_evidence(
        active.id,
        idempotency_key="scoped-model-cache",
        collection="process_executions",
        evidence={"execution_id": "scoped-model-cache", "status": "succeeded"},
        actor="test",
        reason="Verify scoped evidence invalidation.",
    )
    pf.list_tickets(sprint="all")

    assert pf.store._ticket_model_cache[archive_key] is archive_before
    assert pf.store._ticket_model_cache[current_key] is not current_before


def test_evidence_api_preserves_receipts_from_independent_writers(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Concurrent receipts", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    for execution_id in ("send-1", "send-2"):
        response = client.post(
            f"/tickets/{ticket.id}/evidence",
            json={
                "idempotency_key": execution_id,
                "collection": "process_executions",
                "evidence": {"execution_id": execution_id, "status": "succeeded"},
                "actor": "hr-bridge",
                "reason": f"Persist {execution_id}.",
            },
        )
        assert response.status_code == 200

    updated = pf.get_ticket(ticket.id)
    execution_ids = {
        item["execution_id"] for item in updated.outputs.result["process_executions"]
    }
    assert execution_ids == {"send-1", "send-2"}


def test_evidence_api_rejects_reusing_a_key_for_different_evidence(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Immutable receipt", source=TicketSource(tool="test"))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)
    common = {
        "idempotency_key": "send-1",
        "collection": "process_executions",
        "actor": "hr-bridge",
        "reason": "Persist delivery receipt.",
    }

    first = client.post(
        f"/tickets/{ticket.id}/evidence",
        json={**common, "evidence": {"execution_id": "send-1", "status": "succeeded"}},
    )
    conflict = client.post(
        f"/tickets/{ticket.id}/evidence",
        json={**common, "evidence": {"execution_id": "send-1", "status": "failed"}},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "evidence_idempotency_conflict"
