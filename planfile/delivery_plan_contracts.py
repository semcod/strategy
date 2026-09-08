"""Closed contracts for resumable Strategy delivery plans.

The Strategy compiler is deliberately inert.  These models preserve that
boundary while giving Planfile enough structured data to materialize tickets,
record explicit checkpoints and resume after an interrupted process.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

COMPILED_WORK_PLAN_SCHEMA = "subactor.compiled-work-plan/v1"
TICKET_CANDIDATE_SCHEMA = "subactor.ticket-candidate/v1"
TERMINAL_RECEIPT_SCHEMA = "subactor.work-plan-terminal-receipt/v1"
DELIVERY_CHECKPOINT_SCHEMA = "planfile.delivery-checkpoint/v1"
DELIVERY_SPLIT_SCHEMA = "planfile.delivery-plan-split/v1"
DELIVERY_PLAN_STATE_SCHEMA = "planfile.delivery-plan-state/v1"
DELIVERY_PLAN_RESUME_SCHEMA = "planfile.delivery-plan-resume/v1"

_ID = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")
_REFERENCE = re.compile(r"^(?:artifact|knowledge)://[^\s?#]+$")
_RECEIPT_REFERENCE = re.compile(r"^receipt://[^\s?#]+$")
_CHECKPOINT_REFERENCE = re.compile(r"^checkpoint://[^\s?#]+$")
_SAFE_PATH = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$"
)
_BRANCH = re.compile(r"^(?!/)(?!.*(?:\.\.|//|@\{|[~^:?*\[\\]))[A-Za-z0-9._/-]+$")


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(_stable_json(value).encode('utf-8')).hexdigest()}"


def _tuple_of_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("expected a list or tuple")
    return tuple(str(item) for item in value)


def _timestamp(value: object) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("delivery_plan_timestamp_invalid") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("delivery_plan_timestamp_invalid")
    return value


class _ClosedContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True, strict=True)


class DeliveryPlacementV1(_ClosedContract):
    home: Literal["wellmanifest", "subactor", "semcod"]
    shape: Literal["domain_pack", "runtime_service", "both"]
    runtime_owner: Literal["wellmanifest", "subactor", "semcod"]
    adopt: tuple[str, ...]

    @field_validator("adopt", mode="before")
    @classmethod
    def _normalize_adopt(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if not result or len(set(result)) != len(result):
            raise ValueError("delivery_plan_adoption_invalid")
        if any(not re.fullmatch(r"wellmanifest/[a-z0-9][a-z0-9-]{1,79}", item) for item in result):
            raise ValueError("delivery_plan_adoption_invalid")
        return tuple(sorted(result))

    @model_validator(mode="after")
    def _runtime_home(self) -> DeliveryPlacementV1:
        if self.shape == "runtime_service" and (
            self.home == "wellmanifest" or self.runtime_owner == "wellmanifest"
        ):
            raise ValueError("delivery_plan_runtime_home_invalid")
        return self


class DeliveryBudgetV1(_ClosedContract):
    complexity: Literal["XS", "S", "M", "L"]
    estimated_minutes: int = Field(ge=1, le=240)
    max_implementation_files: int = Field(ge=1, le=30)
    max_affected_components: int = Field(ge=1, le=10)
    max_public_interface_changes: int = Field(ge=0, le=10)
    max_runtime_dependencies: int = Field(ge=0, le=10)


class DeliveryTestBindingV1(_ClosedContract):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    kind: Literal["docker", "governance", "node-test", "python-test"]
    target: str

    @field_validator("target")
    @classmethod
    def _safe_target(cls, value: str) -> str:
        if not _SAFE_PATH.fullmatch(value):
            raise ValueError("delivery_plan_test_target_invalid")
        return value


class DeliveryAcceptanceV1(_ClosedContract):
    id: str = Field(pattern=r"^AC-[0-9]{2}$")
    statement: str = Field(min_length=1)
    test_ids: tuple[str, ...]

    @field_validator("test_ids", mode="before")
    @classmethod
    def _normalize_test_ids(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if not result or len(set(result)) != len(result) or any(not _ID.fullmatch(v) for v in result):
            raise ValueError("delivery_plan_acceptance_tests_invalid")
        return tuple(sorted(result))


class TicketCandidateV1(_ClosedContract):
    schema_id: Literal["subactor.ticket-candidate/v1"] = Field(
        default="subactor.ticket-candidate/v1",
        alias="schema",
    )
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    order: int = Field(ge=0, le=1023)
    title: str = Field(min_length=1)
    workstream: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    depends_on: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    placement: DeliveryPlacementV1
    delivery: DeliveryBudgetV1
    components: tuple[str, ...]
    public_interfaces: tuple[str, ...]
    runtime_dependencies: tuple[str, ...]
    acceptance: tuple[DeliveryAcceptanceV1, ...]
    tests: tuple[DeliveryTestBindingV1, ...]
    execution: Literal["inert"]
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    state: Literal["pending", "split_required", "terminal"]
    split_reasons: tuple[str, ...]
    terminal_receipt_ref: str | None

    @field_validator(
        "depends_on",
        "allowed_paths",
        "components",
        "public_interfaces",
        "runtime_dependencies",
        "split_reasons",
        mode="before",
    )
    @classmethod
    def _normalize_string_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result):
            raise ValueError("delivery_plan_candidate_set_duplicate")
        return tuple(sorted(result))

    @field_validator("acceptance", "tests", mode="before")
    @classmethod
    def _normalize_model_tuple(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @model_validator(mode="after")
    def _validate_candidate(self) -> TicketCandidateV1:
        if not self.allowed_paths or any(not _SAFE_PATH.fullmatch(path) for path in self.allowed_paths):
            raise ValueError("delivery_plan_candidate_paths_invalid")
        if not self.components or not self.acceptance or not self.tests:
            raise ValueError("delivery_plan_candidate_evidence_invalid")
        test_ids = {binding.id for binding in self.tests}
        if len(test_ids) != len(self.tests):
            raise ValueError("delivery_plan_candidate_test_duplicate")
        if len({criterion.id for criterion in self.acceptance}) != len(self.acceptance):
            raise ValueError("delivery_plan_candidate_acceptance_duplicate")
        if any(not set(criterion.test_ids).issubset(test_ids) for criterion in self.acceptance):
            raise ValueError("delivery_plan_candidate_acceptance_test_unknown")
        if self.state == "terminal":
            if not self.terminal_receipt_ref or not _RECEIPT_REFERENCE.fullmatch(
                self.terminal_receipt_ref
            ):
                raise ValueError("delivery_plan_candidate_terminal_receipt_invalid")
        elif self.terminal_receipt_ref is not None:
            raise ValueError("delivery_plan_candidate_terminal_receipt_unexpected")
        if (self.state == "split_required") != bool(self.split_reasons):
            raise ValueError("delivery_plan_candidate_split_state_invalid")

        core = self.model_dump(
            mode="json",
            by_alias=True,
            include={
                "schema_id",
                "plan_hash",
                "candidate_key",
                "order",
                "title",
                "workstream",
                "depends_on",
                "allowed_paths",
                "placement",
                "delivery",
                "components",
                "public_interfaces",
                "runtime_dependencies",
                "acceptance",
                "tests",
                "execution",
            },
        )
        if _digest(core) != self.candidate_digest:
            raise ValueError("delivery_plan_candidate_digest_mismatch")
        expected_idempotency = _digest(
            {
                "plan_hash": self.plan_hash,
                "candidate_key": self.candidate_key,
                "candidate_digest": self.candidate_digest,
            }
        )
        if expected_idempotency != self.idempotency_key:
            raise ValueError("delivery_plan_candidate_idempotency_mismatch")
        return self


class CompiledWorkPlanV1(_ClosedContract):
    schema_id: Literal["subactor.compiled-work-plan/v1"] = Field(
        default="subactor.compiled-work-plan/v1",
        alias="schema",
    )
    status: Literal["ready", "split_required"]
    execution: Literal["inert"]
    authority: Literal["none"]
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_ref: str
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    repository: str
    accepted_base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    target_branch: str
    placement: DeliveryPlacementV1
    candidate_count: int = Field(ge=1, le=12)
    pending_count: int = Field(ge=0, le=12)
    split_required: tuple[str, ...]
    terminal_candidates: tuple[str, ...]
    candidates: tuple[TicketCandidateV1, ...]

    @field_validator("split_required", "terminal_candidates", mode="before")
    @classmethod
    def _normalize_key_tuple(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result) or any(not _ID.fullmatch(item) for item in result):
            raise ValueError("delivery_plan_candidate_keys_invalid")
        return tuple(sorted(result))

    @field_validator("candidates", mode="before")
    @classmethod
    def _normalize_candidates(cls, value: object) -> tuple[object, ...]:
        if not isinstance(value, (list, tuple)):
            raise TypeError("expected a list or tuple")
        return tuple(value)

    @field_validator("plan_ref")
    @classmethod
    def _plan_reference(cls, value: str) -> str:
        if not _REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_ref_invalid")
        return value

    @field_validator("repository")
    @classmethod
    def _repository(cls, value: str) -> str:
        if not _REPOSITORY.fullmatch(value):
            raise ValueError("delivery_plan_repository_invalid")
        return value

    @field_validator("target_branch")
    @classmethod
    def _branch(cls, value: str) -> str:
        if not _BRANCH.fullmatch(value):
            raise ValueError("delivery_plan_branch_invalid")
        return value

    @model_validator(mode="after")
    def _validate_graph(self) -> CompiledWorkPlanV1:
        if len(self.candidates) != self.candidate_count:
            raise ValueError("delivery_plan_candidate_count_mismatch")
        keys = [candidate.candidate_key for candidate in self.candidates]
        if len(set(keys)) != len(keys):
            raise ValueError("delivery_plan_candidate_key_duplicate")
        if [candidate.order for candidate in self.candidates] != list(range(len(self.candidates))):
            raise ValueError("delivery_plan_candidate_order_invalid")
        order = {candidate.candidate_key: candidate.order for candidate in self.candidates}
        for candidate in self.candidates:
            if candidate.plan_hash != self.plan_hash or candidate.placement != self.placement:
                raise ValueError("delivery_plan_candidate_binding_mismatch")
            if any(dependency not in order for dependency in candidate.depends_on):
                raise ValueError("delivery_plan_dependency_unknown")
            if any(order[dependency] >= candidate.order for dependency in candidate.depends_on):
                raise ValueError("delivery_plan_dependency_order_invalid")
        split = tuple(sorted(c.candidate_key for c in self.candidates if c.state == "split_required"))
        terminal = tuple(sorted(c.candidate_key for c in self.candidates if c.state == "terminal"))
        if split != self.split_required or terminal != self.terminal_candidates:
            raise ValueError("delivery_plan_candidate_state_projection_mismatch")
        if self.pending_count != len(self.candidates) - len(split) - len(terminal):
            raise ValueError("delivery_plan_pending_count_mismatch")
        if (self.status == "split_required") != bool(split):
            raise ValueError("delivery_plan_status_mismatch")
        return self


class WorkPlanTerminalReceiptV1(_ClosedContract):
    schema_id: Literal["subactor.work-plan-terminal-receipt/v1"] = Field(
        default="subactor.work-plan-terminal-receipt/v1",
        alias="schema",
    )
    receipt_ref: str
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    accepted_base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    outcome: Literal["merged", "no-change"]
    terminal_sha: str = Field(pattern=r"^[a-f0-9]{40}$")

    @field_validator("receipt_ref")
    @classmethod
    def _receipt_reference(cls, value: str) -> str:
        if not _RECEIPT_REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_receipt_ref_invalid")
        return value


class DeliveryCheckpointV1(_ClosedContract):
    schema_id: Literal["planfile.delivery-checkpoint/v1"] = Field(
        default="planfile.delivery-checkpoint/v1",
        alias="schema",
    )
    checkpoint_ref: str
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    sequence: int = Field(ge=1)
    phase: Literal["materialized", "development", "testing", "review", "waiting"]
    head_sha: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    evidence_refs: tuple[str, ...] = ()
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _recorded_timestamp(cls, value: object) -> datetime:
        return _timestamp(value)

    @field_validator("checkpoint_ref")
    @classmethod
    def _checkpoint_reference(cls, value: str) -> str:
        if not _CHECKPOINT_REFERENCE.fullmatch(value):
            raise ValueError("delivery_plan_checkpoint_ref_invalid")
        return value

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _evidence_references(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(set(result)) != len(result) or any(not _REFERENCE.fullmatch(item) for item in result):
            raise ValueError("delivery_plan_checkpoint_evidence_invalid")
        return tuple(sorted(result))


class DeliveryPlanSplitV1(_ClosedContract):
    schema_id: Literal["planfile.delivery-plan-split/v1"] = Field(
        default="planfile.delivery-plan-split/v1",
        alias="schema",
    )
    split_ref: str
    plan_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    plan_hash: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    parent_candidate_key: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    parent_candidate_digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    child_candidate_keys: tuple[str, ...]
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def _recorded_timestamp(cls, value: object) -> datetime:
        return _timestamp(value)

    @field_validator("split_ref")
    @classmethod
    def _split_reference(cls, value: str) -> str:
        if not value.startswith("split://") or any(character.isspace() for character in value):
            raise ValueError("delivery_plan_split_ref_invalid")
        return value

    @field_validator("child_candidate_keys", mode="before")
    @classmethod
    def _children(cls, value: object) -> tuple[str, ...]:
        result = _tuple_of_strings(value)
        if len(result) < 2 or len(set(result)) != len(result) or any(
            not _ID.fullmatch(item) for item in result
        ):
            raise ValueError("delivery_plan_split_children_invalid")
        return tuple(sorted(result))


__all__ = [
    "COMPILED_WORK_PLAN_SCHEMA",
    "DELIVERY_CHECKPOINT_SCHEMA",
    "DELIVERY_PLAN_RESUME_SCHEMA",
    "DELIVERY_PLAN_STATE_SCHEMA",
    "DELIVERY_SPLIT_SCHEMA",
    "TERMINAL_RECEIPT_SCHEMA",
    "TICKET_CANDIDATE_SCHEMA",
    "CompiledWorkPlanV1",
    "DeliveryCheckpointV1",
    "DeliveryPlanSplitV1",
    "TicketCandidateV1",
    "WorkPlanTerminalReceiptV1",
]
