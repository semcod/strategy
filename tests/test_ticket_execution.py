"""Tests for queue-oriented ticket execution metadata."""

from __future__ import annotations

import pytest
import yaml

from planfile import (
    Planfile,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
)
from planfile.core.store import ImmutableTerminalReopenError, TicketUpdatedAtConflictError


def test_legacy_completed_terminal_is_projected_as_done_without_rewriting_yaml(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Historical completed terminal",
        execution=TicketExecution(state="running"),
    )
    sprint_path = tmp_path / ".planfile" / "sprints" / "current.yaml"
    stored = yaml.safe_load(sprint_path.read_text(encoding="utf-8"))
    raw_ticket = stored["sprint"]["tickets"][ticket.id]
    raw_ticket["status"] = "completed"
    raw_ticket["execution"]["state"] = "completed"
    sprint_path.write_text(yaml.safe_dump(stored, sort_keys=False), encoding="utf-8")

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.status == "done"
    assert loaded.execution is not None
    assert loaded.execution.state == "done"
    authoritative = yaml.safe_load(sprint_path.read_text(encoding="utf-8"))
    assert authoritative["sprint"]["tickets"][ticket.id]["status"] == "completed"
    assert authoritative["sprint"]["tickets"][ticket.id]["execution"]["state"] == "completed"


def test_legacy_completed_terminal_is_projected_as_done_without_rewriting_yaml(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Historical completed terminal",
        execution=TicketExecution(state="running"),
    )
    sprint_path = tmp_path / ".planfile" / "sprints" / "current.yaml"
    stored = yaml.safe_load(sprint_path.read_text(encoding="utf-8"))
    raw_ticket = stored["sprint"]["tickets"][ticket.id]
    raw_ticket["status"] = "completed"
    raw_ticket["execution"]["state"] = "completed"
    sprint_path.write_text(yaml.safe_dump(stored, sort_keys=False), encoding="utf-8")

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.status == "done"
    assert loaded.execution is not None
    assert loaded.execution.state == "done"
    authoritative = yaml.safe_load(sprint_path.read_text(encoding="utf-8"))
    assert authoritative["sprint"]["tickets"][ticket.id]["status"] == "completed"
    assert authoritative["sprint"]["tickets"][ticket.id]["execution"]["state"] == "completed"


def test_ticket_round_trip_with_execution_fields(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Bootstrap OpenRouter integration",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending", max_attempts=3),
        inputs=TicketInputs(env_keys=["OPENROUTER_API_KEY"], script="scripts/bootstrap.sh"),
        outputs=TicketOutputs(artifacts=["report.json"]),
    )

    loaded = pf.get_ticket(ticket.id)

    assert loaded is not None
    assert loaded.executor is not None
    assert loaded.executor.kind == "shell"
    assert loaded.executor.handler == "scripts/bootstrap.sh"
    assert loaded.execution is not None
    assert loaded.execution.state == "pending"
    assert loaded.execution.max_attempts == 3
    assert loaded.inputs is not None
    assert loaded.inputs.env_keys == ["OPENROUTER_API_KEY"]
    assert loaded.outputs is not None
    assert loaded.outputs.artifacts == ["report.json"]


def test_next_ticket_respects_dependencies_execution_state_and_priority(tmp_path):
    pf = Planfile(str(tmp_path))

    blocked = pf.create_ticket(
        name="Provide API key",
        priority="normal",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="waiting_input"),
    )

    pf.create_ticket(
        name="Run bootstrap shell",
        priority="critical",
        blocked_by=[blocked.id],
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending"),
    )

    runnable = pf.create_ticket(
        name="Generate pyqual config",
        priority="high",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/generate.sh"),
        execution=TicketExecution(state="ready"),
    )

    next_ticket = pf.next_ticket()
    assert next_ticket is not None
    assert next_ticket.id == runnable.id


def test_next_ticket_can_filter_by_execution_queue(tmp_path):
    pf = Planfile(str(tmp_path))

    default_ticket = pf.create_ticket(
        name="Default queue task",
        priority="critical",
        execution=TicketExecution(queue="default", state="ready"),
    )
    refactor_ticket = pf.create_ticket(
        name="Refactor queue task",
        priority="high",
        execution=TicketExecution(queue="c2004-refactor", state="ready"),
    )

    assert pf.next_ticket().id == default_ticket.id
    filtered = pf.next_ticket(queue="c2004-refactor")
    assert filtered is not None
    assert filtered.id == refactor_ticket.id


def test_next_ticket_unblocks_when_dependency_is_done(tmp_path):
    pf = Planfile(str(tmp_path))

    prerequisite = pf.create_ticket(
        name="Provide API key",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="waiting_input"),
    )
    dependent = pf.create_ticket(
        name="Run bootstrap shell",
        priority="critical",
        blocked_by=[prerequisite.id],
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic"),
        execution=TicketExecution(state="pending"),
    )

    assert pf.next_ticket() is None

    pf.update_ticket(
        prerequisite.id,
        status="done",
        execution=TicketExecution(state="done"),
    )

    next_ticket = pf.next_ticket()
    assert next_ticket is not None
    assert next_ticket.id == dependent.id


def test_ticket_execution_lifecycle_claim_start_complete(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Run bootstrap shell",
        source=TicketSource(tool="shell"),
        executor=TicketExecutor(kind="shell", mode="automatic", handler="scripts/bootstrap.sh"),
        execution=TicketExecution(state="pending"),
    )

    claimed = pf.claim_ticket(ticket.id, assigned_to="koru-shell", lease_seconds=600)
    assert claimed is not None
    assert claimed.execution is not None
    assert claimed.execution.assigned_to == "koru-shell"
    assert claimed.execution.state == "ready"
    assert claimed.execution.lease_expires_at is not None

    started = pf.start_ticket(ticket.id)
    assert started is not None
    assert started.status == "in_progress"
    assert started.execution is not None
    assert started.execution.state == "running"
    assert started.execution.started_at is not None

    completed = pf.complete_ticket(
        ticket.id,
        note="Bootstrap completed successfully",
        artifacts=["reports/bootstrap.json"],
        result={"ok": True},
    )
    assert completed is not None
    assert completed.status == "done"
    assert completed.execution is not None
    assert completed.execution.state == "done"
    assert completed.execution.finished_at is not None
    assert completed.outputs is not None
    assert completed.outputs.notes == ["Bootstrap completed successfully"]
    assert completed.outputs.artifacts == ["reports/bootstrap.json"]
    assert completed.outputs.result == {"ok": True}


def test_ticket_execution_waiting_input_ready_and_fail(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Provide integration credentials",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="pending"),
    )

    waiting = pf.wait_for_input(
        ticket.id,
        prompt="Provide OPENROUTER_API_KEY",
        env_keys=["OPENROUTER_API_KEY"],
    )
    assert waiting is not None
    assert waiting.execution is not None
    assert waiting.execution.state == "waiting_input"
    assert waiting.inputs is not None
    assert waiting.inputs.prompt == "Provide OPENROUTER_API_KEY"
    assert waiting.inputs.env_keys == ["OPENROUTER_API_KEY"]

    ready = pf.ready_ticket(ticket.id)
    assert ready is not None
    assert ready.execution is not None
    assert ready.execution.state == "ready"

    failed = pf.fail_ticket(ticket.id, error="Remote API returned HTTP 502")
    assert failed is not None
    assert failed.execution is not None
    assert failed.execution.state == "failed"
    assert failed.execution.last_error == "Remote API returned HTTP 502"
    assert failed.execution.attempt == 1
    assert failed.status == "failed"


def test_failed_attempt_requeues_until_retry_budget_is_exhausted(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Retry bounded work",
        execution=TicketExecution(state="running", max_attempts=2),
    )

    retryable = pf.fail_ticket(ticket.id, error="temporary", actor="bot:test")
    assert retryable is not None
    assert retryable.status == "open"
    assert retryable.execution.state == "ready"
    assert retryable.execution.attempt == 1
    assert pf.next_ticket().id == ticket.id

    exhausted = pf.fail_ticket(ticket.id, error="permanent", actor="bot:test")
    assert exhausted is not None
    assert exhausted.status == "failed"
    assert exhausted.execution.state == "failed"
    assert exhausted.execution.attempt == 2


@pytest.mark.parametrize("sharded", [False, True])
def test_fail_ticket_rejects_stale_updated_at_without_mutation(tmp_path, sharded):
    pf = Planfile(str(tmp_path))
    if sharded:
        config = pf.store._read_config()
        config["archive"]["enabled"] = False
        pf.store._write_config(config)
        pf.store.migrate_to_sharded_yaml(shard_size=100)
    ticket = pf.create_ticket(
        name="Atomic stale failure guard",
        execution=TicketExecution(state="running", assigned_to="bot:test", max_attempts=2),
    )
    observed_updated_at = ticket.model_dump(mode="json")["updated_at"]
    changed = pf.update_ticket(
        ticket.id,
        priority="high",
        actor="bot:other",
        reason="concurrent_priority_change",
    )
    assert changed is not None
    history_before = list(changed.history)
    events_before = pf.store.operational_events(ticket_id=ticket.id)

    with pytest.raises(
        TicketUpdatedAtConflictError,
        match="ticket_updated_at_precondition_failed",
    ):
        pf.fail_ticket(
            ticket.id,
            error="stale_watchdog_failure",
            actor="bot:watchdog",
            expected_updated_at=observed_updated_at,
        )

    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.priority == "high"
    assert current.status == "open"
    assert current.execution.state == "running"
    assert current.execution.attempt == 0
    assert current.history == history_before
    assert pf.store.operational_events(ticket_id=ticket.id) == events_before


def test_fail_ticket_accepts_updated_at_from_append_only_evidence_projection(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Candidate with evidence",
        execution=TicketExecution(state="running", assigned_to="bot:test", max_attempts=2),
    )
    projected, recorded = pf.append_ticket_evidence(
        ticket.id,
        idempotency_key="heartbeat-1",
        collection="heartbeats",
        evidence={"status": "observed"},
        reason="worker heartbeat",
        actor="bot:test",
    )
    assert recorded is True
    assert projected is not None
    expected_updated_at = projected.model_dump(mode="json")["updated_at"]

    failed = pf.fail_ticket(
        ticket.id,
        error="worker_stopped_after_heartbeat",
        actor="bot:watchdog",
        expected_updated_at=expected_updated_at,
    )

    assert failed is not None
    assert failed.execution.state == "ready"
    assert failed.execution.attempt == 1


@pytest.mark.parametrize("terminal_status", ["done", "canceled", "blocked"])
def test_terminal_status_normalizes_execution_state(tmp_path, terminal_status):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Terminal lifecycle consistency",
        execution=TicketExecution(
            state="waiting_input",
            assigned_to="founder",
            lease_expires_at="2026-07-20T18:00:00Z",
        ),
    )

    terminal = pf.update_ticket(ticket.id, status=terminal_status)

    assert terminal is not None
    assert terminal.status == terminal_status
    assert terminal.execution is not None
    assert terminal.execution.state == terminal_status
    assert terminal.execution.assigned_to is None
    assert terminal.execution.lease_expires_at is None
    assert terminal.execution.finished_at is not None


@pytest.mark.parametrize("terminal_status", ["done", "canceled"])
def test_immutable_terminal_ticket_rejects_ordinary_reopen(tmp_path, terminal_status):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Immutable terminal lifecycle",
        execution=TicketExecution(state="running", assigned_to="bot:test"),
    )
    terminal = pf.update_ticket(ticket.id, status=terminal_status)

    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.update_ticket(
            ticket.id,
            execution=TicketExecution(state="running", assigned_to="bot:late"),
            actor="bot:late",
            reason="stale_worker_update",
        )
    with pytest.raises(ImmutableTerminalReopenError, match="immutable_terminal_reopen"):
        pf.ready_ticket(ticket.id, actor="bot:late", reason="stale_retry")

    current = pf.get_ticket(ticket.id)
    assert current is not None
    assert current.status == terminal_status
    assert current.execution is not None
    assert current.execution.state == terminal_status
    assert current.execution.assigned_to is None


def test_immutable_terminal_ticket_accepts_append_only_evidence(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Completed work")
    pf.update_ticket(ticket.id, status="done")

    updated, recorded = pf.append_ticket_evidence(
        ticket.id,
        idempotency_key="late-verifier:v1",
        collection="evidence",
        evidence={"schema": "test.evidence/v1", "passed": True},
        reason="late_verification",
        actor="bot:verifier",
    )

    assert recorded is True
    assert updated is not None
    assert updated.status == "done"
    assert updated.execution is not None
    assert updated.execution.state == "done"


def test_ready_ticket_reopens_started_ticket_and_clears_stale_execution_claim(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Retry explicit work",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(state="ready", queue="founder"),
    )
    started = pf.start_ticket(ticket.id, assigned_to="founder")
    assert started is not None
    assert started.status == "in_progress"

    ready = pf.ready_ticket(ticket.id)

    assert ready is not None
    assert ready.status == "open"
    assert ready.execution is not None
    assert ready.execution.state == "ready"
    assert ready.execution.assigned_to is None
    assert ready.execution.started_at is None
    assert ready.execution.finished_at is None
    assert ready.execution.lease_expires_at is None


def test_human_response_is_persisted_and_moves_ticket_atomically(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Founder decision",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="waiting_input"),
    )

    ready = pf.respond_ticket(
        ticket.id,
        note="Access approved for the employee.",
        actor="founder",
    )
    assert ready is not None
    assert ready.status == "open"
    assert ready.execution is not None
    assert ready.execution.state == "ready"
    assert ready.outputs is not None
    assert ready.outputs.notes == ["Access approved for the employee."]
    assert ready.history[-1]["reason"] == "human_response"
    assert ready.history[-1]["actor"] == "founder"

    working = pf.respond_ticket(
        ticket.id,
        note="I am still preparing the access details.",
        next_state="in_progress",
        actor="founder",
    )
    assert working is not None
    assert working.status == "in_progress"
    assert working.execution is not None
    assert working.execution.state == "running"
    assert working.execution.assigned_to == "founder"
    assert working.outputs is not None
    assert working.outputs.notes == [
        "Access approved for the employee.",
        "I am still preparing the access details.",
    ]

    with pytest.raises(ValueError, match="ticket_response_required"):
        pf.respond_ticket(ticket.id, note="   ")


def test_human_response_can_preserve_current_status(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Founder adds context without changing work state",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="running", assigned_to="founder"),
        status="in_progress",
    )

    updated = pf.respond_ticket(
        ticket.id,
        note="Additional context only.",
        next_state=None,
        actor="founder",
    )

    assert updated is not None
    assert updated.status == "in_progress"
    assert updated.execution is not None
    assert updated.execution.state == "running"
    assert updated.execution.assigned_to == "founder"
    assert updated.outputs.notes == ["Additional context only."]


def test_response_can_atomically_delegate_with_an_instruction(tmp_path, monkeypatch):
    catalogue = tmp_path / "delegation-actors.json"
    catalogue.write_text('{"actors":[{"id":"marketing-lead","label":"Marketing lead","kind":"human"}]}')
    monkeypatch.setenv("PLANFILE_DELEGATION_ACTORS_FILE", str(catalogue))
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Delegate me",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive", handler="founder"),
        execution=TicketExecution(queue="founder", state="waiting_input"),
    )

    delegated = pf.respond_ticket(
        ticket.id,
        note="Use the company YouTube channel and report moderation actions.",
        delegate_to="marketing-lead",
        delegate_kind="human",
    )

    assert delegated.execution.queue == "marketing-lead"
    assert delegated.execution.state == "ready"
    assert delegated.execution.assigned_to is None
    assert delegated.executor.handler == "marketing-lead"
    assert delegated.outputs.notes[-1].startswith("Use the company YouTube")


def test_response_rejects_actor_outside_delegation_catalogue(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Do not delegate me", source=TicketSource(tool="human"))

    with pytest.raises(ValueError, match="ticket_delegate_not_allowed:unknown-bot"):
        pf.respond_ticket(ticket.id, note="Try invalid target", delegate_to="unknown-bot")


def test_block_ticket_clears_running_execution_claim(tmp_path):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Run external task",
        source=TicketSource(tool="shell"),
        execution=TicketExecution(state="pending"),
    )

    started = pf.start_ticket(ticket.id, assigned_to="worker-1")
    assert started.execution.state == "running"

    blocked = pf.block_ticket(ticket.id, reason="external precondition missing")
    assert blocked is not None
    assert blocked.status == "blocked"
    assert blocked.description == "BLOCKED: external precondition missing"
    assert blocked.execution is not None
    assert blocked.execution.state == "blocked"
    assert blocked.execution.assigned_to is None
    assert blocked.execution.lease_expires_at is None
    assert blocked.execution.finished_at is not None


def test_wait_for_input_appends_note_to_outputs_notes(tmp_path):
    """`pf.wait_for_input(..., note=...)` should append to outputs.notes
    so an agent can record *why* it is escalating to a human (PLF-koru #7).
    """
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Need env var",
        source=TicketSource(tool="human"),
        executor=TicketExecutor(kind="human", mode="interactive"),
        execution=TicketExecution(state="pending"),
    )

    waiting = pf.wait_for_input(
        ticket.id,
        prompt="Provide OPENROUTER_API_KEY",
        env_keys=["OPENROUTER_API_KEY"],
        note="agent diagnostic: tried 3 fallback keys, all 401",
    )
    assert waiting is not None
    assert waiting.outputs is not None
    assert waiting.outputs.notes == [
        "agent diagnostic: tried 3 fallback keys, all 401"
    ]
    # Subsequent calls should *append* rather than replace.
    waiting2 = pf.wait_for_input(
        ticket.id,
        prompt="Updated prompt",
        note="second escalation: rate limit reached at provider",
    )
    assert waiting2 is not None
    assert waiting2.outputs is not None
    assert waiting2.outputs.notes == [
        "agent diagnostic: tried 3 fallback keys, all 401",
        "second escalation: rate limit reached at provider",
    ]


def test_append_note_helper_preserves_artifacts_and_result(tmp_path):
    """`_append_note` should additively grow notes while preserving
    artifacts and result fields (shared by ready/input/update flows)."""
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="With outputs",
        source=TicketSource(tool="human"),
        outputs=TicketOutputs(
            artifacts=["report.json"],
            notes=["initial"],
            result={"score": 0.9},
        ),
    )
    outputs = pf._append_note(ticket, "follow-up observation")
    assert outputs.notes == ["initial", "follow-up observation"]
    assert outputs.artifacts == ["report.json"]
    assert outputs.result == {"score": 0.9}


def test_annotate_blockers_marks_resolved_blockers(tmp_path):
    """`planfile ticket show` should annotate `blocked_by` with each
    blocker's current status, surfacing already-resolved blockers under
    `resolved_blockers` (PLF-koru improvement #3).
    """
    from planfile.cli.groups.ticket.commands import _annotate_blockers

    pf = Planfile(str(tmp_path))
    blocker = pf.create_ticket(name="Blocker", source=TicketSource(tool="human"))
    blocked = pf.create_ticket(
        name="Blocked",
        source=TicketSource(tool="human"),
        blocked_by=[blocker.id],
    )
    pf.complete_ticket(blocker.id)

    data = pf.get_ticket(blocked.id).model_dump(mode="json", exclude_none=True)
    _annotate_blockers(pf, data)

    assert data["blocker_states"] == {blocker.id: "done"}
    assert data["resolved_blockers"] == [blocker.id]


def test_annotate_blockers_handles_missing_blocker(tmp_path):
    """A blocker referenced by ID but never created should be flagged
    `missing` instead of crashing the renderer."""
    from planfile.cli.groups.ticket.commands import _annotate_blockers

    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="Ghost-blocked",
        source=TicketSource(tool="human"),
        blocked_by=["PLF-DOES-NOT-EXIST"],
    )
    data = pf.get_ticket(ticket.id).model_dump(mode="json", exclude_none=True)
    _annotate_blockers(pf, data)
    assert data["blocker_states"] == {"PLF-DOES-NOT-EXIST": "missing"}
    # No resolved_blockers field because nothing actually resolved.
    assert "resolved_blockers" not in data


def test_annotate_blockers_is_noop_when_no_blockers(tmp_path):
    """No `blocked_by` → no annotation keys added (clean ticket show)."""
    from planfile.cli.groups.ticket.commands import _annotate_blockers

    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Free", source=TicketSource(tool="human"))
    data = pf.get_ticket(ticket.id).model_dump(mode="json", exclude_none=True)
    _annotate_blockers(pf, data)
    assert "blocker_states" not in data
    assert "resolved_blockers" not in data
