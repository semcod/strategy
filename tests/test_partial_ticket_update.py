"""A PATCH must change only the fields it sends.

Observed 2026-09-03 on a running deployment: twelve supervisor plans sat in
`waiting_input` for up to 152 hours with an automatic recovery that could never
see them. The recovery keys on `inputs.api_body`; the producer wrote it, and a
later unrelated PATCH — one that only meant to set `uri_processes` — erased it,
because FastAPI had filled every omitted field of `TicketInputs` with its model
default before the store wrote the section through.

The same shape erased `execution.last_error` and `execution.started_at`
elsewhere. These tests pin the section-merge behaviour that stops it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from planfile.api import server

    server.get_planfile.cache_clear() if hasattr(server.get_planfile, "cache_clear") else None
    return TestClient(server.app)


def create(client, **overrides):
    payload = {"name": "Supervisor plan: verify the seam", "priority": "high", **overrides}
    response = client.post("/tickets", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def get_inputs(client, ticket_id):
    response = client.get(f"/tickets/{ticket_id}")
    assert response.status_code == 200, response.text
    return response.json().get("inputs") or {}


def get_execution(client, ticket_id):
    response = client.get(f"/tickets/{ticket_id}")
    assert response.status_code == 200, response.text
    return response.json().get("execution") or {}


def patch(client, ticket_id, body):
    response = client.patch(
        f"/tickets/{ticket_id}",
        json={"actor": "test:agent", "reason": "covering the partial-update seam", **body},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_partial_inputs_patch_keeps_the_fields_it_did_not_send(client):
    envelope = {"schema": "subactor.supervisor-ticket-input/v1", "apply": False, "goal": "ship it"}
    ticket_id = create(client, inputs={"api_body": envelope, "prompt": "original prompt"})
    assert get_inputs(client, ticket_id)["api_body"] == envelope

    # The exact shape that erased it: a write that only means to set processes.
    patch(client, ticket_id, {"inputs": {"uri_processes": []}})

    stored = get_inputs(client, ticket_id)
    assert stored["api_body"] == envelope, "an unmentioned section field must survive"
    assert stored["prompt"] == "original prompt"


def test_a_partial_execution_patch_keeps_the_failure_reason(client):
    ticket_id = create(client)
    patch(client, ticket_id, {"execution": {"state": "running", "last_error": "bridge_422:rejected"}})
    assert get_execution(client, ticket_id)["last_error"] == "bridge_422:rejected"

    # A heartbeat-shaped write that names only the queue.
    patch(client, ticket_id, {"execution": {"queue": "project-operator-bot"}})

    execution = get_execution(client, ticket_id)
    assert execution["last_error"] == "bridge_422:rejected", "a heartbeat must not erase the reason"
    assert execution["queue"] == "project-operator-bot"


def test_a_sent_field_still_overwrites(client):
    ticket_id = create(client, inputs={"prompt": "first"})
    patch(client, ticket_id, {"inputs": {"prompt": "second"}})
    assert get_inputs(client, ticket_id)["prompt"] == "second"


def test_an_explicit_null_still_clears_a_field(client):
    ticket_id = create(client, inputs={"prompt": "first"})
    patch(client, ticket_id, {"inputs": {"prompt": None}})
    # Omission is inert; sending null is still how a caller clears a field.
    assert "prompt" not in get_inputs(client, ticket_id)


def test_untouched_sections_are_left_alone(client):
    ticket_id = create(client, inputs={"prompt": "keep me"})
    patch(client, ticket_id, {"execution": {"queue": "somewhere"}})
    assert get_inputs(client, ticket_id)["prompt"] == "keep me"


def test_a_patch_that_sends_no_section_changes_nothing_in_them(client):
    envelope = {"schema": "subactor.supervisor-ticket-input/v1", "apply": False}
    ticket_id = create(client, inputs={"api_body": envelope})
    patch(client, ticket_id, {"priority": "low"})
    assert get_inputs(client, ticket_id)["api_body"] == envelope
