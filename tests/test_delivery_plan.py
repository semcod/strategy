from __future__ import annotations

import hashlib
import json
from datetime import timezone, datetime

import pytest
from pydantic import ValidationError

from planfile import Planfile
from planfile.delivery_plan import DeliveryPlanError
from planfile.delivery_plan_contracts import CompiledWorkPlanV1

PLAN_HASH = "sha256:" + "a" * 64
BASE_SHA = "b" * 40


def _digest(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


def _candidate(
    key: str,
    order: int,
    *,
    depends_on: list[str] | None = None,
    state: str = "pending",
    paths: list[str] | None = None,
) -> dict:
    core = {
        "schema": "subactor.ticket-candidate/v1",
        "plan_hash": PLAN_HASH,
        "candidate_key": key,
        "order": order,
        "title": f"Deliver {key}",
        "workstream": "runtime",
        "depends_on": sorted(depends_on or []),
        "allowed_paths": sorted(paths or [f"src/{key}.py"]),
        "placement": {
            "home": "semcod",
            "shape": "runtime_service",
            "runtime_owner": "semcod",
            "adopt": ["wellmanifest/dsl", "wellmanifest/new-project"],
        },
        "delivery": {
            "complexity": "S",
            "estimated_minutes": 20,
            "max_implementation_files": 2,
            "max_affected_components": 1,
            "max_public_interface_changes": 1,
            "max_runtime_dependencies": 0,
        },
        "components": ["delivery-plan"],
        "public_interfaces": ["Planfile.materialize_delivery_plan"],
        "runtime_dependencies": [],
        "acceptance": [
            {
                "id": "AC-01",
                "statement": "The bounded slice has explicit verification.",
                "test_ids": ["python-suite"],
            }
        ],
        "tests": [
            {"id": "python-suite", "kind": "python-test", "target": "tests/test_delivery_plan.py"}
        ],
        "execution": "inert",
    }
    candidate_digest = _digest(core)
    return {
        **core,
        "candidate_digest": candidate_digest,
        "idempotency_key": _digest(
            {
                "plan_hash": PLAN_HASH,
                "candidate_key": key,
                "candidate_digest": candidate_digest,
            }
        ),
        "state": state,
        "split_reasons": ["complexity_time_limit"] if state == "split_required" else [],
        "terminal_receipt_ref": None,
    }


def _plan(candidates: list[dict]) -> dict:
    split_required = sorted(
        candidate["candidate_key"]
        for candidate in candidates
        if candidate["state"] == "split_required"
    )
    terminal = sorted(
        candidate["candidate_key"]
        for candidate in candidates
        if candidate["state"] == "terminal"
    )
    return {
        "schema": "subactor.compiled-work-plan/v1",
        "status": "split_required" if split_required else "ready",
        "execution": "inert",
        "authority": "none",
        "plan_id": "resumable-delivery",
        "plan_ref": "artifact://semcod/planfile/delivery-plan-r1",
        "plan_hash": PLAN_HASH,
        "repository": "semcod/planfile",
        "accepted_base_sha": BASE_SHA,
        "target_branch": "main",
        "placement": {
            "home": "semcod",
            "shape": "runtime_service",
            "runtime_owner": "semcod",
            "adopt": ["wellmanifest/dsl", "wellmanifest/new-project"],
        },
        "candidate_count": len(candidates),
        "pending_count": len(candidates) - len(split_required) - len(terminal),
        "split_required": split_required,
        "terminal_candidates": terminal,
        "candidates": candidates,
    }


def _receipt(candidate: dict, *, receipt_ref: str = "receipt://github/semcod/planfile/101") -> dict:
    return {
        "schema": "subactor.work-plan-terminal-receipt/v1",
        "receipt_ref": receipt_ref,
        "plan_hash": PLAN_HASH,
        "candidate_key": candidate["candidate_key"],
        "candidate_digest": candidate["candidate_digest"],
        "accepted_base_sha": BASE_SHA,
        "outcome": "merged",
        "terminal_sha": "c" * 40,
    }


def test_materialization_is_atomic_idempotent_and_execution_inert(tmp_path) -> None:
    runtime = _candidate("runtime-core", 0)
    facade = _candidate("package-facade", 1, depends_on=["runtime-core"])
    backend = Planfile(str(tmp_path))

    first = backend.materialize_delivery_plan(_plan([runtime, facade]))
    second = backend.materialize_delivery_plan(_plan([runtime, facade]))

    assert first == second
    assert first["revision"] == 1
    assert len(backend.list_tickets(sprint="all")) == 2
    runtime_ticket = backend.get_ticket(first["candidates"]["runtime-core"]["ticket_id"])
    facade_ticket = backend.get_ticket(first["candidates"]["package-facade"]["ticket_id"])
    assert runtime_ticket is not None and runtime_ticket.executor is None
    assert runtime_ticket.source.context["authority"] == "none"
    assert facade_ticket is not None and facade_ticket.blocked_by == [runtime_ticket.id]
    persisted = tmp_path / ".planfile" / "delivery-plans" / "resumable-delivery.json"
    assert json.loads(persisted.read_text())["schema"] == "planfile.delivery-plan-state/v1"


def test_materialization_recovers_exact_ids_after_missing_state_replace(tmp_path) -> None:
    candidates = [_candidate("runtime-core", 0), _candidate("package-facade", 1)]
    backend = Planfile(str(tmp_path))
    first = backend.materialize_delivery_plan(_plan(candidates))
    state_path = tmp_path / ".planfile" / "delivery-plans" / "resumable-delivery.json"
    state_path.unlink()

    recovered = backend.materialize_delivery_plan(_plan(candidates))

    assert {
        key: node["ticket_id"] for key, node in recovered["candidates"].items()
    } == {key: node["ticket_id"] for key, node in first["candidates"].items()}
    assert len(backend.list_tickets(sprint="all")) == 2


def test_materialization_requires_and_deduplicates_compiled_terminal_receipt(tmp_path) -> None:
    candidate = _candidate("already-delivered", 0)
    receipt = _receipt(candidate)
    candidate["state"] = "terminal"
    candidate["terminal_receipt_ref"] = receipt["receipt_ref"]
    plan = _plan([candidate])
    backend = Planfile(str(tmp_path))

    with pytest.raises(DeliveryPlanError, match="delivery_plan_terminal_receipt_missing"):
        backend.materialize_delivery_plan(plan)
    state = backend.materialize_delivery_plan(plan, terminal_receipts=[receipt, receipt])

    ticket = backend.get_ticket(state["candidates"]["already-delivered"]["ticket_id"])
    assert ticket is not None and ticket.status.value == "done"
    assert ticket.outputs.completion_receipt == receipt


def test_checkpoint_and_terminal_receipt_resume_partial_completion(tmp_path) -> None:
    runtime = _candidate("runtime-core", 0)
    facade = _candidate("package-facade", 1, depends_on=["runtime-core"])
    backend = Planfile(str(tmp_path))
    state = backend.materialize_delivery_plan(_plan([runtime, facade]))
    checkpoint = {
        "schema": "planfile.delivery-checkpoint/v1",
        "checkpoint_ref": "checkpoint://semcod/planfile/runtime-core/1",
        "plan_id": state["plan_id"],
        "plan_hash": state["plan_hash"],
        "candidate_key": "runtime-core",
        "candidate_digest": runtime["candidate_digest"],
        "sequence": 1,
        "phase": "testing",
        "head_sha": "d" * 40,
        "evidence_refs": ["artifact://semcod/planfile/test-report-r1"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    checkpointed = backend.checkpoint_delivery_candidate(checkpoint)
    duplicate = backend.checkpoint_delivery_candidate(checkpoint)
    assert duplicate == checkpointed
    resume = backend.resume_delivery_plan(state["plan_id"])
    assert resume["ready"][0]["checkpoint"]["checkpoint_ref"] == checkpoint["checkpoint_ref"]
    assert resume["waiting"][0]["candidate_key"] == "package-facade"
    assert resume["authority"] == "none"

    terminal = backend.record_delivery_terminal_receipt(state["plan_id"], _receipt(runtime))
    repeated = backend.record_delivery_terminal_receipt(state["plan_id"], _receipt(runtime))
    assert repeated == terminal
    assert backend.materialize_delivery_plan(_plan([runtime, facade])) == terminal
    resumed = backend.resume_delivery_plan(state["plan_id"])
    assert resumed["terminal"] == ["runtime-core"]
    assert resumed["ready"][0]["candidate_key"] == "package-facade"
    ticket = backend.get_ticket(terminal["candidates"]["runtime-core"]["ticket_id"])
    assert ticket is not None and ticket.status.value == "done"
    assert ticket.outputs.completion_receipt["receipt_ref"].startswith("receipt://")


def test_conflicting_checkpoint_and_receipt_fail_closed(tmp_path) -> None:
    candidate = _candidate("runtime-core", 0)
    backend = Planfile(str(tmp_path))
    state = backend.materialize_delivery_plan(_plan([candidate]))
    checkpoint = {
        "schema": "planfile.delivery-checkpoint/v1",
        "checkpoint_ref": "checkpoint://semcod/planfile/runtime-core/1",
        "plan_id": state["plan_id"],
        "plan_hash": state["plan_hash"],
        "candidate_key": "runtime-core",
        "candidate_digest": candidate["candidate_digest"],
        "sequence": 1,
        "phase": "testing",
        "head_sha": None,
        "evidence_refs": [],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    backend.checkpoint_delivery_candidate(checkpoint)
    with pytest.raises(DeliveryPlanError, match="delivery_plan_checkpoint_conflict"):
        backend.checkpoint_delivery_candidate({**checkpoint, "phase": "review"})

    backend.record_delivery_terminal_receipt(state["plan_id"], _receipt(candidate))
    with pytest.raises(DeliveryPlanError, match="delivery_plan_receipt_conflict"):
        backend.record_delivery_terminal_receipt(
            state["plan_id"],
            _receipt(candidate, receipt_ref="receipt://github/semcod/planfile/other"),
        )


def test_split_state_links_children_and_rewires_successor(tmp_path) -> None:
    parent = _candidate("oversized-parent", 0, state="split_required")
    child_a = _candidate("bounded-child-a", 1)
    child_b = _candidate("bounded-child-b", 2)
    successor = _candidate("integration-slice", 3, depends_on=["oversized-parent"])
    backend = Planfile(str(tmp_path))
    state = backend.materialize_delivery_plan(_plan([parent, child_a, child_b, successor]))
    split = {
        "schema": "planfile.delivery-plan-split/v1",
        "split_ref": "split://semcod/planfile/oversized-parent/1",
        "plan_id": state["plan_id"],
        "plan_hash": state["plan_hash"],
        "parent_candidate_key": "oversized-parent",
        "parent_candidate_digest": parent["candidate_digest"],
        "child_candidate_keys": ["bounded-child-a", "bounded-child-b"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    linked = backend.record_delivery_split(split)
    assert backend.record_delivery_split(split) == linked
    parent_node = linked["candidates"]["oversized-parent"]
    assert parent_node["status"] == "split"
    assert parent_node["child_candidate_keys"] == ["bounded-child-a", "bounded-child-b"]
    assert linked["candidates"]["integration-slice"]["depends_on"] == [
        "bounded-child-a",
        "bounded-child-b",
    ]
    parent_ticket_id = parent_node["ticket_id"]
    child_ticket = backend.get_ticket(linked["candidates"]["bounded-child-a"]["ticket_id"])
    assert child_ticket is not None and child_ticket.parent == parent_ticket_id
    resume = backend.resume_delivery_plan(state["plan_id"])
    assert {item["candidate_key"] for item in resume["ready"]} == {
        "bounded-child-a",
        "bounded-child-b",
    }
    assert resume["split_active"] == ["oversized-parent"]
    assert resume["waiting"][0]["waiting_on"] == ["bounded-child-a", "bounded-child-b"]

    backend.record_delivery_terminal_receipt(
        state["plan_id"],
        _receipt(child_a, receipt_ref="receipt://github/semcod/planfile/child-a"),
    )
    backend.record_delivery_terminal_receipt(
        state["plan_id"],
        _receipt(child_b, receipt_ref="receipt://github/semcod/planfile/child-b"),
    )
    completed_split = backend.resume_delivery_plan(state["plan_id"])
    assert completed_split["split_complete"] == ["oversized-parent"]
    assert completed_split["ready"][0]["candidate_key"] == "integration-slice"


def test_compiled_contract_rejects_embedded_tool_authority() -> None:
    candidate = _candidate("runtime-core", 0)
    candidate["command"] = "git push --force"
    with pytest.raises(ValidationError):
        CompiledWorkPlanV1.model_validate(_plan([candidate]))

    plan = _plan([_candidate("runtime-core", 0)])
    plan["authority"] = "shell"
    with pytest.raises(ValidationError):
        CompiledWorkPlanV1.model_validate(plan)
