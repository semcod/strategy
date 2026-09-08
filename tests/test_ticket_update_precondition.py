"""Conditional observer writes cannot replace newer worker evidence."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from planfile import Planfile, TicketExecution, TicketOutputs
from planfile.api import server


@pytest.fixture(params=["yaml", "sharded-yaml"])
def context(tmp_path, monkeypatch, request):
    pf = Planfile(str(tmp_path))
    if request.param == "sharded-yaml":
        pf.store.migrate_to_sharded_yaml(shard_size=100)
    ticket = pf.create_ticket(
        name="Publication observation",
        execution=TicketExecution(state="ready", max_attempts=2),
    )
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    return pf, ticket, TestClient(server.app)


@pytest.mark.parametrize("operation", ["update", "complete"])
@pytest.mark.parametrize("revision", [None, "", "   "])
def test_conditional_write_requires_revision(context, operation, revision):
    pf, ticket, client = context
    body = {} if revision is None else {"expected_updated_at": revision}
    response = client.post(f"/tickets/{ticket.id}/{operation}-if-current", json=body)
    assert response.status_code == 422
    assert pf.get_ticket(ticket.id).updated_at == ticket.updated_at


@pytest.mark.parametrize("operation", ["update", "complete"])
def test_conditional_write_accepts_current_revision(context, operation):
    pf, ticket, client = context
    body = {"expected_updated_at": ticket.model_dump(mode="json")["updated_at"]}
    body.update({"priority": "high"} if operation == "update" else {"result": {"observed": True}})
    response = client.post(f"/tickets/{ticket.id}/{operation}-if-current", json=body)
    assert response.status_code == 200
    current = pf.get_ticket(ticket.id)
    assert current.updated_at != ticket.updated_at
    if operation == "update":
        assert current.priority == "high"
        assert current.execution.state == "ready"
    else:
        assert current.status == "done"
        assert current.outputs.result == {"observed": True}
    assert f"ticket.{operation}.expected_updated_at" in client.get("/health").json()["capabilities"]


@pytest.mark.parametrize("operation", ["update", "complete"])
@pytest.mark.parametrize("interleave", [False, True])
def test_new_worker_receipt_survives_stale_observation(context, monkeypatch, operation, interleave):
    pf, ticket, client = context
    revision = ticket.model_dump(mode="json")["updated_at"]
    original_update = pf.update_ticket
    evidence = {"process_executions": [{"process_id": "publish", "receipt_id": "failed"}],
                "publication_authorization": {"status": "consumed_failed"}}

    def worker_update():
        original_update(
            ticket.id, status="failed", execution=TicketExecution(state="failed", attempt=1),
            outputs=TicketOutputs(result=evidence), actor="bot:worker", reason="apply_failed",
        )

    if interleave:
        # The worker wins after the API/high-level pre-read but before the
        # store mutation. A pre-read comparison alone cannot pass this case.
        def race(ticket_id, **updates):
            worker_update()
            return original_update(ticket_id, **updates)
        monkeypatch.setattr(pf, "update_ticket", race)
    else:
        worker_update()

    async def unexpected_event(*_args):
        pytest.fail("a rejected write must not broadcast a successful change")
    monkeypatch.setattr(server, "_broadcast_ticket_event", unexpected_event)
    body = {"expected_updated_at": revision, "actor": "bot:observer", "reason": "observation"}
    body.update({"execution": {"state": "ready"}, "outputs": {"result": {"observed": True}}}
                if operation == "update" else {"result": {"observed": True}})
    response = client.post(f"/tickets/{ticket.id}/{operation}-if-current", json=body)
    assert response.status_code == 409
    assert response.json() == {"detail": "ticket_updated_at_precondition_failed"}
    current = pf.get_ticket(ticket.id)
    assert current.status == "failed"
    assert current.execution.state == "failed"
    assert current.execution.attempt == 1
    assert current.outputs.result == evidence
    assert current.history[-1]["actor"] == "bot:worker"


def test_conditional_completion_keeps_governed_receipt_gate(context):
    pf, ticket, client = context
    ticket = pf.update_ticket(ticket.id, labels=["process-envelope:v2"])
    response = client.post(
        f"/tickets/{ticket.id}/complete-if-current",
        json={"expected_updated_at": ticket.model_dump(mode="json")["updated_at"]},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "completion_receipt_required"}
    assert pf.get_ticket(ticket.id).status == "open"
