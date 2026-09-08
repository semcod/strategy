"""Durable, idempotent materialization of inert Strategy delivery plans."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn, cast

from planfile.core.fastio import _atomic_write_text
from planfile.core.models import Ticket, TicketExecution, TicketOutputs, TicketSource, TicketStatus
from planfile.delivery_plan_contracts import (
    DELIVERY_PLAN_RESUME_SCHEMA,
    DELIVERY_PLAN_STATE_SCHEMA,
    CompiledWorkPlanV1,
    DeliveryCheckpointV1,
    DeliveryPlacementV1,
    DeliveryPlanSplitV1,
    TicketCandidateV1,
    WorkPlanTerminalReceiptV1,
)


class DeliveryPlanError(ValueError):
    """A stable delivery-plan contract or persistence failure."""


def _fail(code: str) -> NoReturn:
    raise DeliveryPlanError(code)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(model: Any) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        model.model_dump(mode="json", by_alias=True, exclude_none=False),
    )


class DeliveryPlanRepository:
    """Persist delivery DAG state next to Planfile's authoritative ticket store.

    Every mutation shares Planfile's cross-process store lock and replaces one
    complete JSON state file.  Ticket creation is replay-safe: candidate source
    bindings are sufficient to recover when the ticket batch landed but a power
    loss happened before the state file replace.
    """

    def __init__(self, store: Any):
        self.store = store
        self.base_dir = Path(store.base_dir) / "delivery-plans"

    @staticmethod
    def _plan_id(value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", str(value or "")):
            _fail("delivery_plan_id_invalid")
        return str(value)

    def _path(self, plan_id: str) -> Path:
        return self.base_dir / f"{self._plan_id(plan_id)}.json"

    def _read_unlocked(self, plan_id: str) -> dict[str, Any] | None:
        try:
            value = json.loads(self._path(plan_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise DeliveryPlanError("delivery_plan_state_unreadable") from exc
        self._validate_state(value)
        return cast(dict[str, Any], value)

    def _write_unlocked(self, state: dict[str, Any]) -> None:
        self._validate_state(state)
        content = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        _atomic_write_text(self._path(str(state["plan_id"])), content)

    @staticmethod
    def _validate_state(value: object) -> None:
        if not isinstance(value, dict):
            _fail("delivery_plan_state_invalid")
        state = cast(dict[str, Any], value)
        expected = {
            "schema",
            "revision",
            "plan_id",
            "plan_ref",
            "plan_hash",
            "repository",
            "accepted_base_sha",
            "target_branch",
            "placement",
            "created_at",
            "updated_at",
            "candidates",
        }
        if set(state) != expected or state.get("schema") != DELIVERY_PLAN_STATE_SCHEMA:
            _fail("delivery_plan_state_invalid")
        if not isinstance(state.get("revision"), int) or state["revision"] < 1:
            _fail("delivery_plan_state_revision_invalid")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", str(state.get("plan_id") or "")):
            _fail("delivery_plan_state_identity_invalid")
        if not re.fullmatch(
            r"(?:artifact|knowledge)://[^\s?#]+", str(state.get("plan_ref") or "")
        ):
            _fail("delivery_plan_state_identity_invalid")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", str(state.get("plan_hash") or "")):
            _fail("delivery_plan_state_identity_invalid")
        if not re.fullmatch(
            r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(state.get("repository") or "")
        ):
            _fail("delivery_plan_state_identity_invalid")
        if not re.fullmatch(r"[a-f0-9]{40}", str(state.get("accepted_base_sha") or "")):
            _fail("delivery_plan_state_identity_invalid")
        if not re.fullmatch(
            r"(?!/)(?!.*(?:\.\.|//|@\{|[~^:?*\[\\]))[A-Za-z0-9._/-]+",
            str(state.get("target_branch") or ""),
        ):
            _fail("delivery_plan_state_identity_invalid")
        DeliveryPlacementV1.model_validate(state.get("placement"))
        try:
            created_at = datetime.fromisoformat(str(state["created_at"]))
            updated_at = datetime.fromisoformat(str(state["updated_at"]))
        except ValueError as exc:
            raise DeliveryPlanError("delivery_plan_state_time_invalid") from exc
        if created_at.tzinfo is None or updated_at.tzinfo is None or updated_at < created_at:
            _fail("delivery_plan_state_time_invalid")
        candidates = state.get("candidates")
        if not isinstance(candidates, dict) or not candidates:
            _fail("delivery_plan_state_candidates_invalid")
        ticket_ids: set[str] = set()
        checkpoint_refs: set[str] = set()
        receipt_refs: set[str] = set()
        split_refs: set[str] = set()
        for key, node in candidates.items():
            if not isinstance(node, dict) or set(node) != {
                "candidate",
                "ticket_id",
                "status",
                "parent_candidate_key",
                "child_candidate_keys",
                "depends_on",
                "checkpoints",
                "terminal_receipt",
                "split",
            }:
                _fail("delivery_plan_state_candidate_invalid")
            candidate = TicketCandidateV1.model_validate(node["candidate"])
            if (
                key != candidate.candidate_key
                or candidate.plan_hash != state["plan_hash"]
                or candidate.placement.model_dump(mode="json") != state["placement"]
            ):
                _fail("delivery_plan_state_candidate_binding_mismatch")
            ticket_id = str(node.get("ticket_id") or "")
            if not ticket_id or ticket_id in ticket_ids:
                _fail("delivery_plan_state_ticket_binding_invalid")
            ticket_ids.add(ticket_id)
            if node.get("status") not in {
                "materialized",
                "checkpointed",
                "split_required",
                "split",
                "terminal",
            }:
                _fail("delivery_plan_state_candidate_status_invalid")
            children = node.get("child_candidate_keys")
            dependencies = node.get("depends_on")
            checkpoints = node.get("checkpoints")
            if (
                not isinstance(children, list)
                or len(set(children)) != len(children)
                or not all(isinstance(item, str) for item in children)
            ):
                _fail("delivery_plan_state_children_invalid")
            if (
                not isinstance(dependencies, list)
                or len(set(dependencies)) != len(dependencies)
                or not all(isinstance(item, str) for item in dependencies)
            ):
                _fail("delivery_plan_state_dependencies_invalid")
            if not isinstance(checkpoints, list):
                _fail("delivery_plan_state_checkpoints_invalid")
            for sequence, checkpoint in enumerate(checkpoints, start=1):
                parsed = DeliveryCheckpointV1.model_validate(checkpoint)
                if (
                    parsed.candidate_key != key
                    or parsed.plan_id != state["plan_id"]
                    or parsed.plan_hash != state["plan_hash"]
                    or parsed.candidate_digest != candidate.candidate_digest
                    or parsed.sequence != sequence
                    or parsed.checkpoint_ref in checkpoint_refs
                ):
                    _fail("delivery_plan_state_checkpoint_binding_mismatch")
                checkpoint_refs.add(parsed.checkpoint_ref)
            receipt = node.get("terminal_receipt")
            if receipt is not None:
                parsed_receipt = WorkPlanTerminalReceiptV1.model_validate(receipt)
                if (
                    parsed_receipt.candidate_key != key
                    or parsed_receipt.plan_hash != state["plan_hash"]
                    or parsed_receipt.accepted_base_sha != state["accepted_base_sha"]
                    or parsed_receipt.candidate_digest != candidate.candidate_digest
                    or parsed_receipt.receipt_ref in receipt_refs
                ):
                    _fail("delivery_plan_state_receipt_binding_mismatch")
                receipt_refs.add(parsed_receipt.receipt_ref)
            split = node.get("split")
            if split is not None:
                parsed_split = DeliveryPlanSplitV1.model_validate(split)
                if (
                    parsed_split.parent_candidate_key != key
                    or parsed_split.plan_id != state["plan_id"]
                    or parsed_split.plan_hash != state["plan_hash"]
                    or parsed_split.parent_candidate_digest != candidate.candidate_digest
                    or tuple(node["child_candidate_keys"]) != parsed_split.child_candidate_keys
                    or parsed_split.split_ref in split_refs
                ):
                    _fail("delivery_plan_state_split_binding_mismatch")
                split_refs.add(parsed_split.split_ref)
            status = node["status"]
            if status == "materialized" and (checkpoints or receipt is not None or split is not None):
                _fail("delivery_plan_state_candidate_status_invalid")
            if status == "checkpointed" and (not checkpoints or receipt is not None or split is not None):
                _fail("delivery_plan_state_candidate_status_invalid")
            if status == "split_required" and (
                candidate.state != "split_required"
                or checkpoints
                or receipt is not None
                or split is not None
            ):
                _fail("delivery_plan_state_candidate_status_invalid")
            if status == "split" and (
                candidate.state != "split_required" or checkpoints or split is None
            ):
                _fail("delivery_plan_state_candidate_status_invalid")
            if status == "terminal" and (receipt is None or split is not None):
                _fail("delivery_plan_state_candidate_status_invalid")
        known = set(candidates)
        for key, node in candidates.items():
            parent = node.get("parent_candidate_key")
            if parent is not None and parent not in known:
                _fail("delivery_plan_state_parent_unknown")
            if any(child not in known for child in node["child_candidate_keys"]):
                _fail("delivery_plan_state_child_unknown")
            if any(dependency not in known for dependency in node["depends_on"]):
                _fail("delivery_plan_state_dependency_unknown")
            if key in node["depends_on"] or key in node["child_candidate_keys"]:
                _fail("delivery_plan_state_cycle_invalid")
            for child in node["child_candidate_keys"]:
                if candidates[child]["parent_candidate_key"] != key:
                    _fail("delivery_plan_state_child_binding_mismatch")
            parent = node["parent_candidate_key"]
            if parent is not None and key not in candidates[parent]["child_candidate_keys"]:
                _fail("delivery_plan_state_parent_binding_mismatch")
        DeliveryPlanRepository._validate_dependency_dag(candidates)

    @staticmethod
    def _validate_dependency_dag(candidates: dict[str, dict[str, Any]]) -> None:
        pending = {
            key: {str(dependency) for dependency in node["depends_on"]}
            for key, node in candidates.items()
        }
        while pending:
            ready = {key for key, dependencies in pending.items() if not dependencies}
            if not ready:
                _fail("delivery_plan_state_dependency_cycle")
            for key in ready:
                pending.pop(key)
            for dependencies in pending.values():
                dependencies.difference_update(ready)

    @staticmethod
    def _receipt_map(
        plan: CompiledWorkPlanV1,
        receipts: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> dict[str, WorkPlanTerminalReceiptV1]:
        candidates = {candidate.candidate_key: candidate for candidate in plan.candidates}
        by_candidate: dict[str, WorkPlanTerminalReceiptV1] = {}
        by_ref: dict[str, WorkPlanTerminalReceiptV1] = {}
        for raw in receipts:
            receipt = WorkPlanTerminalReceiptV1.model_validate(raw)
            candidate = candidates.get(receipt.candidate_key)
            if candidate is None:
                _fail("delivery_plan_receipt_candidate_unknown")
            if (
                receipt.plan_hash != plan.plan_hash
                or receipt.candidate_digest != candidate.candidate_digest
                or receipt.accepted_base_sha != plan.accepted_base_sha
            ):
                _fail("delivery_plan_receipt_stale")
            previous = by_candidate.get(receipt.candidate_key)
            if previous is not None and previous != receipt:
                _fail("delivery_plan_receipt_conflict")
            ref_owner = by_ref.get(receipt.receipt_ref)
            if ref_owner is not None and ref_owner != receipt:
                _fail("delivery_plan_receipt_ref_conflict")
            by_candidate[receipt.candidate_key] = receipt
            by_ref[receipt.receipt_ref] = receipt
        for candidate in plan.candidates:
            if candidate.state == "terminal":
                terminal_receipt = by_candidate.get(candidate.candidate_key)
                if (
                    terminal_receipt is not None
                    and terminal_receipt.receipt_ref != candidate.terminal_receipt_ref
                ):
                    _fail("delivery_plan_terminal_receipt_conflict")
            elif candidate.candidate_key in by_candidate:
                _fail("delivery_plan_receipt_for_nonterminal_candidate")
        return by_candidate

    @staticmethod
    def _candidate_context(record: dict[str, Any]) -> dict[str, Any]:
        source = record.get("source")
        if not isinstance(source, dict):
            return {}
        context = source.get("context")
        return context if isinstance(context, dict) else {}

    def _existing_ticket_bindings_unlocked(
        self,
        plan: CompiledWorkPlanV1,
    ) -> dict[str, dict[str, Any]]:
        expected = {candidate.candidate_key: candidate for candidate in plan.candidates}
        found: dict[str, dict[str, Any]] = {}
        for record in self.store.ticket_records(sprint="all"):
            context = self._candidate_context(record)
            if context.get("delivery_plan_id") != plan.plan_id:
                continue
            source = record.get("source")
            if not isinstance(source, dict) or source.get("tool") != "subactor.strategy":
                _fail("delivery_plan_existing_candidate_conflict")
            key = str(context.get("candidate_key") or "")
            candidate = expected.get(key)
            if candidate is None:
                _fail("delivery_plan_existing_candidate_unknown")
            if (
                context.get("plan_hash") != plan.plan_hash
                or context.get("candidate_digest") != candidate.candidate_digest
                or context.get("idempotency_key") != candidate.idempotency_key
            ):
                _fail("delivery_plan_existing_candidate_conflict")
            if key in found:
                _fail("delivery_plan_existing_candidate_duplicate")
            found[key] = record
        return found

    @staticmethod
    def _ticket_for(
        candidate: TicketCandidateV1,
        ticket_id: str,
        dependency_ids: list[str],
        receipt: WorkPlanTerminalReceiptV1 | None,
        plan: CompiledWorkPlanV1,
    ) -> Ticket:
        context = {
            "delivery_plan_id": plan.plan_id,
            "delivery_plan_ref": plan.plan_ref,
            "plan_hash": plan.plan_hash,
            "candidate_key": candidate.candidate_key,
            "candidate_digest": candidate.candidate_digest,
            "idempotency_key": candidate.idempotency_key,
            "workstream": candidate.workstream,
            "execution": "inert",
            "authority": "none",
        }
        labels = [
            "delivery-plan",
            f"plan:{plan.plan_id}",
            f"candidate:{candidate.candidate_key}",
            f"workstream:{candidate.workstream}",
        ]
        execution_state = "pending"
        status = TicketStatus.open
        outputs = None
        if candidate.state == "split_required":
            execution_state = "waiting_input"
            labels.append("split-required")
        elif candidate.state == "terminal":
            execution_state = "done"
            status = TicketStatus.done
            if receipt is None:
                _fail("delivery_plan_terminal_receipt_missing")
            outputs = TicketOutputs(completion_receipt=_dump(receipt))
        return Ticket(
            id=ticket_id,
            name=candidate.title,
            status=status,
            description=(
                f"Materialized from {plan.plan_ref}; candidate {candidate.candidate_key}. "
                "Execution authority is intentionally absent."
            ),
            labels=labels,
            files=list(candidate.allowed_paths),
            acceptance_criteria=[criterion.statement for criterion in candidate.acceptance],
            blocked_by=dependency_ids,
            source=TicketSource(tool="subactor.strategy", version="work-plan/v1", context=context),
            execution=TicketExecution(state=execution_state),
            outputs=outputs,
        )

    @staticmethod
    def _node(
        candidate: TicketCandidateV1,
        ticket_id: str,
        receipt: WorkPlanTerminalReceiptV1 | None,
    ) -> dict[str, Any]:
        status = {
            "pending": "materialized",
            "split_required": "split_required",
            "terminal": "terminal",
        }[candidate.state]
        return {
            "candidate": _dump(candidate),
            "ticket_id": ticket_id,
            "status": status,
            "parent_candidate_key": None,
            "child_candidate_keys": [],
            "depends_on": list(candidate.depends_on),
            "checkpoints": [],
            "terminal_receipt": _dump(receipt) if receipt is not None else None,
            "split": None,
        }

    def materialize(
        self,
        compiled_plan: dict[str, Any],
        *,
        terminal_receipts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> dict[str, Any]:
        """Create or recover the exact ticket DAG and return its durable state."""

        plan = CompiledWorkPlanV1.model_validate(compiled_plan)
        receipts = self._receipt_map(plan, terminal_receipts)
        with self.store.mutation_lock():
            current = self._read_unlocked(plan.plan_id)
            if current is not None:
                return self._reconcile_unlocked(current, plan, receipts)

            if any(
                candidate.state == "terminal" and candidate.candidate_key not in receipts
                for candidate in plan.candidates
            ):
                _fail("delivery_plan_terminal_receipt_missing")

            existing = self._existing_ticket_bindings_unlocked(plan)
            missing = [c for c in plan.candidates if c.candidate_key not in existing]
            reserved = iter(self.store._reserve_ids_unlocked(len(missing)))
            ticket_ids = {
                candidate.candidate_key: str(existing[candidate.candidate_key]["id"])
                if candidate.candidate_key in existing
                else next(reserved)
                for candidate in plan.candidates
            }
            created = [
                self._ticket_for(
                    candidate,
                    ticket_ids[candidate.candidate_key],
                    [ticket_ids[key] for key in candidate.depends_on],
                    receipts.get(candidate.candidate_key),
                    plan,
                )
                for candidate in missing
            ]
            if created:
                self.store._create_tickets_bulk_unlocked(created)
            timestamp = _now()
            state = {
                "schema": DELIVERY_PLAN_STATE_SCHEMA,
                "revision": 1,
                "plan_id": plan.plan_id,
                "plan_ref": plan.plan_ref,
                "plan_hash": plan.plan_hash,
                "repository": plan.repository,
                "accepted_base_sha": plan.accepted_base_sha,
                "target_branch": plan.target_branch,
                "placement": plan.placement.model_dump(mode="json"),
                "created_at": timestamp,
                "updated_at": timestamp,
                "candidates": {
                    candidate.candidate_key: self._node(
                        candidate,
                        ticket_ids[candidate.candidate_key],
                        receipts.get(candidate.candidate_key),
                    )
                    for candidate in plan.candidates
                },
            }
            self._write_unlocked(state)
            return copy.deepcopy(state)

    def _reconcile_unlocked(
        self,
        current: dict[str, Any],
        plan: CompiledWorkPlanV1,
        receipts: dict[str, WorkPlanTerminalReceiptV1],
    ) -> dict[str, Any]:
        identity = (
            current["plan_hash"],
            current["plan_ref"],
            current["repository"],
            current["accepted_base_sha"],
            current["target_branch"],
        )
        expected = (
            plan.plan_hash,
            plan.plan_ref,
            plan.repository,
            plan.accepted_base_sha,
            plan.target_branch,
        )
        if identity != expected:
            _fail("delivery_plan_identity_conflict")
        candidates = {candidate.candidate_key: candidate for candidate in plan.candidates}
        if set(candidates) != set(current["candidates"]):
            _fail("delivery_plan_candidate_set_conflict")
        changed = False
        for key, candidate in candidates.items():
            node = current["candidates"][key]
            stored = TicketCandidateV1.model_validate(node["candidate"])
            if stored.candidate_digest != candidate.candidate_digest:
                _fail("delivery_plan_candidate_conflict")
            receipt = receipts.get(key)
            if receipt is None:
                if candidate.state == "terminal":
                    stored_receipt = node.get("terminal_receipt")
                    if stored_receipt is None:
                        _fail("delivery_plan_terminal_receipt_missing")
                    parsed_receipt = WorkPlanTerminalReceiptV1.model_validate(stored_receipt)
                    if parsed_receipt.receipt_ref != candidate.terminal_receipt_ref:
                        _fail("delivery_plan_terminal_receipt_conflict")
                continue
            if node["status"] in {"split", "split_required"}:
                _fail("delivery_plan_receipt_for_split_candidate")
            previous = node.get("terminal_receipt")
            if previous is not None:
                if WorkPlanTerminalReceiptV1.model_validate(previous) != receipt:
                    _fail("delivery_plan_receipt_conflict")
                continue
            if any(
                other.get("terminal_receipt", {}).get("receipt_ref") == receipt.receipt_ref
                for other in current["candidates"].values()
                if isinstance(other.get("terminal_receipt"), dict)
            ):
                _fail("delivery_plan_receipt_ref_conflict")
            self._complete_ticket_unlocked(str(node["ticket_id"]), receipt)
            node["terminal_receipt"] = _dump(receipt)
            node["status"] = "terminal"
            changed = True
        if changed:
            current["revision"] += 1
            current["updated_at"] = _now()
            self._write_unlocked(current)
        return copy.deepcopy(current)

    def _complete_ticket_unlocked(
        self,
        ticket_id: str,
        receipt: WorkPlanTerminalReceiptV1,
    ) -> None:
        ticket = self.store.get_ticket(ticket_id)
        if ticket is None:
            _fail("delivery_plan_ticket_missing")
        existing = ticket.outputs.completion_receipt if ticket.outputs else None
        serialized = _dump(receipt)
        if str(ticket.status.value) == "done":
            if existing != serialized:
                _fail("delivery_plan_ticket_terminal_conflict")
            return
        outputs_data = ticket.outputs.model_dump(mode="python") if ticket.outputs else {}
        outputs_data["completion_receipt"] = serialized
        updated = self.store._update_ticket_unlocked(
            ticket_id,
            status="done",
            execution=TicketExecution(state="done"),
            outputs=TicketOutputs(**outputs_data),
            reason="delivery_plan_terminal_receipt",
            actor="planfile.delivery-plan",
        )
        if updated is None:
            _fail("delivery_plan_ticket_missing")

    def get(self, plan_id: str) -> dict[str, Any] | None:
        state = self._read_unlocked(plan_id)
        return copy.deepcopy(state) if state is not None else None

    def record_checkpoint(self, checkpoint_value: dict[str, Any]) -> dict[str, Any]:
        checkpoint = DeliveryCheckpointV1.model_validate(checkpoint_value)
        with self.store.mutation_lock():
            state = self._read_unlocked(checkpoint.plan_id)
            if state is None:
                _fail("delivery_plan_not_found")
            node = state["candidates"].get(checkpoint.candidate_key)
            if node is None:
                _fail("delivery_plan_checkpoint_candidate_unknown")
            candidate = TicketCandidateV1.model_validate(node["candidate"])
            if (
                checkpoint.plan_hash != state["plan_hash"]
                or checkpoint.candidate_digest != candidate.candidate_digest
            ):
                _fail("delivery_plan_checkpoint_stale")
            if node["status"] not in {"materialized", "checkpointed"}:
                _fail("delivery_plan_checkpoint_state_invalid")
            for existing in node["checkpoints"]:
                parsed = DeliveryCheckpointV1.model_validate(existing)
                if parsed.checkpoint_ref != checkpoint.checkpoint_ref:
                    continue
                if parsed != checkpoint:
                    _fail("delivery_plan_checkpoint_conflict")
                return copy.deepcopy(state)
            expected_sequence = len(node["checkpoints"]) + 1
            if checkpoint.sequence != expected_sequence:
                _fail("delivery_plan_checkpoint_sequence_invalid")
            node["checkpoints"].append(_dump(checkpoint))
            node["status"] = "checkpointed"
            state["revision"] += 1
            state["updated_at"] = _now()
            self._write_unlocked(state)
            return copy.deepcopy(state)

    def record_terminal_receipt(self, plan_id: str, receipt_value: dict[str, Any]) -> dict[str, Any]:
        receipt = WorkPlanTerminalReceiptV1.model_validate(receipt_value)
        with self.store.mutation_lock():
            state = self._read_unlocked(plan_id)
            if state is None:
                _fail("delivery_plan_not_found")
            node = state["candidates"].get(receipt.candidate_key)
            if node is None:
                _fail("delivery_plan_receipt_candidate_unknown")
            candidate = TicketCandidateV1.model_validate(node["candidate"])
            if (
                receipt.plan_hash != state["plan_hash"]
                or receipt.accepted_base_sha != state["accepted_base_sha"]
                or receipt.candidate_digest != candidate.candidate_digest
            ):
                _fail("delivery_plan_receipt_stale")
            if node["status"] in {"split", "split_required"}:
                _fail("delivery_plan_receipt_for_split_candidate")
            previous = node.get("terminal_receipt")
            if previous is not None:
                if WorkPlanTerminalReceiptV1.model_validate(previous) != receipt:
                    _fail("delivery_plan_receipt_conflict")
                return copy.deepcopy(state)
            if any(
                other.get("terminal_receipt", {}).get("receipt_ref") == receipt.receipt_ref
                for other in state["candidates"].values()
                if isinstance(other.get("terminal_receipt"), dict)
            ):
                _fail("delivery_plan_receipt_ref_conflict")
            self._complete_ticket_unlocked(str(node["ticket_id"]), receipt)
            node["terminal_receipt"] = _dump(receipt)
            node["status"] = "terminal"
            state["revision"] += 1
            state["updated_at"] = _now()
            self._write_unlocked(state)
            return copy.deepcopy(state)

    def record_split(self, split_value: dict[str, Any]) -> dict[str, Any]:
        """Link an oversized candidate to already materialized bounded children."""

        split = DeliveryPlanSplitV1.model_validate(split_value)
        with self.store.mutation_lock():
            state = self._read_unlocked(split.plan_id)
            if state is None:
                _fail("delivery_plan_not_found")
            parent = state["candidates"].get(split.parent_candidate_key)
            if parent is None:
                _fail("delivery_plan_split_parent_unknown")
            parent_candidate = TicketCandidateV1.model_validate(parent["candidate"])
            if (
                split.plan_hash != state["plan_hash"]
                or split.parent_candidate_digest != parent_candidate.candidate_digest
            ):
                _fail("delivery_plan_split_stale")
            if parent.get("split") is not None:
                if DeliveryPlanSplitV1.model_validate(parent["split"]) != split:
                    _fail("delivery_plan_split_conflict")
                return copy.deepcopy(state)
            if parent["status"] != "split_required":
                _fail("delivery_plan_split_state_invalid")
            children = [state["candidates"].get(key) for key in split.child_candidate_keys]
            if any(child is None for child in children):
                _fail("delivery_plan_split_child_unknown")
            for child in children:
                assert child is not None
                if child["status"] == "split_required" or child["parent_candidate_key"] not in {
                    None,
                    split.parent_candidate_key,
                }:
                    _fail("delivery_plan_split_child_invalid")
                if split.parent_candidate_key in child["depends_on"]:
                    _fail("delivery_plan_split_dependency_cycle")
                child["parent_candidate_key"] = split.parent_candidate_key

            parent["status"] = "split"
            parent["child_candidate_keys"] = list(split.child_candidate_keys)
            parent["split"] = _dump(split)
            for node in state["candidates"].values():
                if split.parent_candidate_key not in node["depends_on"]:
                    continue
                node["depends_on"] = sorted(
                    {
                        *(
                            dependency
                            for dependency in node["depends_on"]
                            if dependency != split.parent_candidate_key
                        ),
                        *split.child_candidate_keys,
                    }
                )
            self._validate_state(state)
            child_ids = [str(child["ticket_id"]) for child in children if child is not None]
            parent_ticket = self.store.get_ticket(str(parent["ticket_id"]))
            if parent_ticket is None:
                _fail("delivery_plan_ticket_missing")
            updated_parent = self.store._update_ticket_unlocked(
                str(parent["ticket_id"]),
                children=child_ids,
                blocked_by=child_ids,
                execution=TicketExecution(state="waiting_input"),
                reason="delivery_plan_candidate_split",
                actor="planfile.delivery-plan",
            )
            if updated_parent is None:
                _fail("delivery_plan_ticket_missing")
            for child in children:
                assert child is not None
                updated_child = self.store._update_ticket_unlocked(
                    str(child["ticket_id"]),
                    parent=str(parent["ticket_id"]),
                    reason="delivery_plan_candidate_split_child",
                    actor="planfile.delivery-plan",
                )
                if updated_child is None:
                    _fail("delivery_plan_ticket_missing")
            for node in state["candidates"].values():
                if split.parent_candidate_key not in node["candidate"]["depends_on"]:
                    continue
                dependency_ids = [
                    str(state["candidates"][dependency]["ticket_id"])
                    for dependency in node["depends_on"]
                ]
                updated = self.store._update_ticket_unlocked(
                    str(node["ticket_id"]),
                    blocked_by=dependency_ids,
                    reason="delivery_plan_split_dependency_rewire",
                    actor="planfile.delivery-plan",
                )
                if updated is None:
                    _fail("delivery_plan_ticket_missing")
            state["revision"] += 1
            state["updated_at"] = _now()
            self._write_unlocked(state)
            return copy.deepcopy(state)

    def resume(self, plan_id: str) -> dict[str, Any]:
        """Return a deterministic continuation frontier from persisted DSL state."""

        state = self._read_unlocked(plan_id)
        if state is None:
            _fail("delivery_plan_not_found")
        candidates = state["candidates"]

        def completed(key: str, seen: frozenset[str] = frozenset()) -> bool:
            if key in seen:
                _fail("delivery_plan_state_cycle_invalid")
            node = candidates[key]
            if node["status"] == "terminal":
                return True
            if node["status"] == "split":
                return all(completed(child, seen | {key}) for child in node["child_candidate_keys"])
            return False

        ready: list[dict[str, Any]] = []
        waiting: list[dict[str, Any]] = []
        split_required: list[str] = []
        split_active: list[str] = []
        split_complete: list[str] = []
        terminal: list[str] = []
        for key, node in sorted(
            candidates.items(), key=lambda item: int(item[1]["candidate"]["order"])
        ):
            if node["status"] == "terminal":
                terminal.append(key)
                continue
            if node["status"] == "split_required":
                split_required.append(key)
                continue
            if node["status"] == "split":
                (split_complete if completed(key) else split_active).append(key)
                continue
            checkpoint = node["checkpoints"][-1] if node["checkpoints"] else None
            item = {
                "candidate_key": key,
                "ticket_id": node["ticket_id"],
                "checkpoint": checkpoint,
                "waiting_on": [
                    dependency for dependency in node["depends_on"] if not completed(dependency)
                ],
            }
            (waiting if item["waiting_on"] else ready).append(item)
        return {
            "schema": DELIVERY_PLAN_RESUME_SCHEMA,
            "plan_id": state["plan_id"],
            "plan_hash": state["plan_hash"],
            "revision": state["revision"],
            "ready": ready,
            "waiting": waiting,
            "split_required": split_required,
            "split_active": split_active,
            "split_complete": split_complete,
            "terminal": sorted(terminal),
            "execution": "inert",
            "authority": "none",
        }


__all__ = ["DeliveryPlanError", "DeliveryPlanRepository"]
