"""planfile — universal ticket standard for developer toolchains.

This package provides:
- Strategy and sprint modeling in YAML
- Ticket-based project management (CRUD, import, sync)
- Task execution with intelligent model selection
- Integration with various LLM providers
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.125"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

from datetime import timezone, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

# Core models (single source of truth)
from planfile.core.models import (
    Goal,
    ModelHints,
    ModelTier,
    QualityGate,
    Sprint,
    Strategy,
    Task,
    TaskPattern,
    TaskType,
    Ticket,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
    TicketStatus,
    TicketUriProcess,
)
from planfile.core.store import PlanfileStore
from planfile.delegation import DelegationActor, load_delegation_actors
from planfile.delivery_plan import DeliveryPlanError, DeliveryPlanRepository
from planfile.delivery_plan_contracts import (
    CompiledWorkPlanV1,
    DeliveryCheckpointV1,
    DeliveryPlanSplitV1,
    TicketCandidateV1,
    WorkPlanTerminalReceiptV1,
)
from planfile.dsl import DSLExecutor, DSLParser, DSLResult
from planfile.testql_integration import (
    build_testql_tickets,
    run_testql_validation,
    sync_testql_tickets,
    upsert_testql_tickets,
)
from planfile.ticket_validation import validate_planfile_tickets
from planfile.todo_sync import sync_todo_checkboxes_from_planfile

# Backward compat aliases
StrategyV1 = Strategy
StrategyV2 = Strategy
ModelTierV2 = ModelTier

# Lazy loading for executors to improve startup performance
if TYPE_CHECKING:
    from planfile import executor_standalone, runner
    from planfile.executor_standalone import (
        LLMClient,
        StrategyExecutor,
        TaskResult,
        create_litellm_client,
        create_openai_client,
        execute_strategy,
    )
    from planfile.runner import load_valid_strategy, run_strategy, verify_strategy_post_execution


class Planfile:
    """Main entry point — convenience wrapper around PlanfileStore."""

    MAX_BULK_TICKETS = 50

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    def __init__(self, project_path: str = "."):
        self.store = PlanfileStore(project_path)
        if not self.store.is_initialized():
            self.store.init()
        self.store.ensure_forensic_log_projection()

    @property
    def configuration(self):
        """Return the safe, typed project-configuration facade."""
        from planfile.core.configuration import ConfigurationManager

        return ConfigurationManager(self)

    def delegation_actors(self) -> tuple[DelegationActor, ...]:
        """Return the configured closed set of valid delegation targets."""
        return load_delegation_actors(self.store.project_dir)

    def resolve_delegation_actor(self, actor_id: str) -> DelegationActor | None:
        return next((actor for actor in self.delegation_actors() if actor.id == actor_id), None)

    @classmethod
    def auto_discover(cls, start_path: str = ".") -> "Planfile":
        """Find .planfile/ in CWD or parent directories."""
        path = Path(start_path).resolve()
        while path != path.parent:
            if (path / ".planfile").exists():
                return cls(str(path))
            path = path.parent
        return cls(start_path)  # init in CWD

    def create_ticket(self, name: str, **kwargs) -> Ticket:
        return self.create_ticket_deduplicated(name, **kwargs)[0]

    @staticmethod
    def _ticket_dedupe_label(dedupe_key: str | None, labels: list[str]) -> str | None:
        if str(dedupe_key or "").strip():
            return f"dedupe:{str(dedupe_key).strip()}"
        # A stable dedupe label must win over occurrence labels such as
        # incident:<operation_id>. Producers intentionally keep both.
        return next((label for label in labels if str(label).startswith("dedupe:") and str(label)[7:]), None)

    def create_ticket_deduplicated(self, name: str, **kwargs) -> tuple[Ticket, bool]:
        """Atomically create a ticket or return its live dedupe-key owner."""
        dedupe_key = kwargs.pop("dedupe_key", None)
        labels = list(kwargs.pop("labels", None) or [])
        dedupe_label = self._ticket_dedupe_label(dedupe_key, labels)
        if dedupe_label and dedupe_label not in labels:
            labels.append(dedupe_label)
        if labels:
            kwargs["labels"] = labels
        with self.store.mutation_lock():
            if dedupe_label:
                live = [
                    record for record in self.store.ticket_records(sprint="all")
                    if dedupe_label in (record.get("labels") or [])
                    and str(record.get("status") or "") not in {"done", "canceled"}
                ]
                if live:
                    oldest = min(live, key=lambda record: str(record.get("created_at") or ""))
                    existing = self.store.get_ticket(str(oldest.get("id") or ""))
                    if existing:
                        return existing, False
            ticket_id = self.store._next_id_unlocked()
            ticket = Ticket(id=ticket_id, name=name, **kwargs)
            return self.store._create_ticket_unlocked(ticket), True

    def get_ticket(self, ticket_id: str, *, repair_index: bool = True):
        return self.store.get_ticket(ticket_id, repair_index=repair_index)

    def list_tickets(self, **filters):
        return self.store.list_tickets(**filters)

    # ── Planfile runnability contract ─────────────────────────────────────────
    # A ticket may be handed to an autonomous queue only when ALL hold:
    #   status == open · execution.state ∈ {pending, ready, ""} · every blocked_by is done/canceled
    #   · not autonomy-frontier · not waiting on a human/resource (actor:human / needs-human / waiting:*)
    #   · on the active CURRENT_GOAL (if any).
    # `blocked_by` models a ticket→ticket DEPENDENCY; `waiting:*` / `autonomy-frontier` model a
    # RESOURCE / autonomy-boundary wait — a distinct axis (never forced into blocked_by). Without
    # this, next_ticket kept re-serving the same un-doable ticket (pick→fail→reopen→pick), which is
    # why koru looped on frontier tickets regardless of the work:// control plane.
    _RUNNABLE_EXEC_STATES = {"pending", "ready", ""}
    _DEP_SATISFIED_STATES = {"done", "canceled"}

    @staticmethod
    def _autonomy_skip(ticket: "Ticket") -> str:
        """Autonomy-boundary / resource-wait reason this ticket is not agent-runnable, or ""."""
        import os
        if os.environ.get("PLANFILE_NO_AUTONOMY_FILTER") == "1":
            return ""
        require_envelope = os.environ.get("PLANFILE_REQUIRE_PROCESS_ENVELOPE", "").strip().lower() in {
            "1", "true", "yes", "on",
        }
        if require_envelope:
            manifest = ticket.inputs.process_manifest if ticket.inputs else None
            if not isinstance(manifest, dict) or manifest.get("schema") != "subactor.process-envelope.v2":
                return "process-envelope-required"
            definitions = manifest.get("definitions")
            valid = (
                bool(str(manifest.get("reason") or "").strip())
                and bool(str(manifest.get("requested_by") or "").strip())
                and isinstance(definitions, dict)
                and all(isinstance(definitions.get(kind), list) and definitions[kind]
                        for kind in ("aql", "eql", "oql", "uri"))
            )
            if not valid:
                return "process-envelope-invalid"
        labels = [str(l).lower() for l in (ticket.labels or [])]
        if "autonomy-frontier" in labels:
            return "autonomy-frontier"
        if "actor:human" in labels:
            return "actor:human"
        for l in labels:
            if l.startswith("waiting:") or l.startswith("needs-human"):
                return l
        return ""

    @staticmethod
    def _autonomy_blocked(ticket: "Ticket") -> bool:
        """Boolean form of :meth:`_autonomy_skip` (frozen frontier / human / resource wait)."""
        return bool(Planfile._autonomy_skip(ticket))

    @staticmethod
    def _goal_frozen(ticket: "Ticket") -> bool:
        """Goal-delivery mode: when a delivery goal is active (env ``CURRENT_GOAL``), only
        goal-related tickets are runnable — the rest is frozen so the queue can't escape the goal
        into unrelated code. No-op when ``CURRENT_GOAL`` is unset. Env-only (payload-only) by design
        so planfile core stays decoupled from any runtime state file."""
        import os
        goal = os.environ.get("CURRENT_GOAL") or ""
        if not goal:
            return False
        domain = goal.split(".")[0]
        labels = [str(l).lower() for l in (ticket.labels or [])]
        if f"goal:{goal}" in labels or f"goal:{domain}" in labels:
            return False
        blob = f"{ticket.name} {ticket.description or ''} {' '.join(labels)}".lower()
        return domain not in blob

    def runnability_skip_reason(
        self,
        ticket: "Ticket",
        queue: str | None = None,
        *,
        ticket_by_id: dict[str, "Ticket"] | None = None,
    ) -> str:
        """"" if the ticket satisfies the runnability contract (may be served to a queue), else a
        short machine-readable reason (``exec_state:<s>`` / ``autonomy-frontier`` / ``actor:human`` /
        ``waiting:<x>`` / ``goal-frozen`` / ``blocked_by:<ID>`` / ``queue:<q>``). Assumes the ticket
        is already status=open (the caller filters status)."""
        exec_state = (ticket.execution.state if ticket.execution else "") or ""
        if exec_state not in self._RUNNABLE_EXEC_STATES:
            return f"exec_state:{exec_state}"
        autonomy = self._autonomy_skip(ticket)
        if autonomy:
            return autonomy
        if self._goal_frozen(ticket):
            return "goal-frozen"
        if queue and ((ticket.execution.queue if ticket.execution else "default") != queue):
            return f"queue:{queue}"
        for blocked_id in (ticket.blocked_by or []):
            dep = (
                ticket_by_id.get(blocked_id)
                if ticket_by_id is not None
                else self.get_ticket(blocked_id)
            )
            dep_status = (dep.status.value if dep and hasattr(dep.status, "value") else str(dep.status)) if dep else None
            if not dep or dep_status not in self._DEP_SATISFIED_STATES:
                return f"blocked_by:{blocked_id}"
        return ""

    @staticmethod
    def _ticket_sort_key(ticket: "Ticket"):
        """Bug-first ordering: priority, then bugs before features, then age, then id."""
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        is_bug = 0 if ticket.labels and "bug" in ticket.labels else 1
        return (priority_order.get(str(ticket.priority), 99), is_bug, str(ticket.created_at), ticket.id)

    def _ticket_snapshot_with_dependencies(self, tickets: list["Ticket"]) -> dict[str, "Ticket"]:
        """Extend one current snapshot with directly located archived dependencies."""
        ticket_by_id = {ticket.id: ticket for ticket in tickets}
        if not hasattr(self, "store"):
            return ticket_by_id
        locations = self.store._history_locations()
        dependency_ids = {
            dependency
            for ticket in tickets
            for dependency in (ticket.blocked_by or [])
            if dependency not in ticket_by_id and dependency in locations
        }
        for dependency in dependency_ids:
            archived = self.get_ticket(dependency)
            if archived is not None:
                ticket_by_id[dependency] = archived
        return ticket_by_id

    def runnable_report(self, sprint: str = "current", queue: str | None = None) -> dict:
        """Explain runnability for every open ticket — for ``planfile ticket next --debug`` and
        dashboards: ``{selected, servable: [ids], skipped: [{id, reason}]}`` (servable in serve order)."""
        servable, skipped = [], []
        tickets = self.list_tickets(sprint=sprint)
        ticket_by_id = self._ticket_snapshot_with_dependencies(tickets)
        for ticket in tickets:
            status = ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status)
            if status != "open":
                continue
            reason = self.runnability_skip_reason(
                ticket,
                queue=queue,
                ticket_by_id=ticket_by_id,
            )
            (skipped.append({"id": ticket.id, "reason": reason}) if reason else servable.append(ticket))
        servable.sort(key=self._ticket_sort_key)
        return {"selected": servable[0].id if servable else None,
                "servable": [t.id for t in servable], "skipped": skipped}

    def next_ticket(self, sprint: str = "current", queue: str | None = None) -> Ticket | None:
        """Return the next RUNNABLE ticket (Planfile runnability contract) for queue-like workflows,
        bug-first within priority. Skips frozen-frontier / human-waiting / resource-waiting / off-goal
        / dependency-blocked tickets so an autonomous queue never loops on un-doable work."""
        tickets = self.list_tickets(sprint=sprint)
        ticket_by_id = self._ticket_snapshot_with_dependencies(tickets)
        runnable = (
            ticket
            for ticket in tickets
            if (ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status))
            == "open"
            and not self.runnability_skip_reason(
                ticket,
                queue=queue,
                ticket_by_id=ticket_by_id,
            )
        )
        return min(runnable, key=self._ticket_sort_key, default=None)

    def update_ticket(
        self,
        ticket_id: str,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
        **updates,
    ):
        """Delegate with optional reason (why status/etc changed) and actor (who/by)."""
        return self.store.update_ticket(
            ticket_id,
            reason=reason,
            actor=actor,
            expected_updated_at=expected_updated_at,
            **updates,
        )

    def append_ticket_evidence(
        self,
        ticket_id: str,
        *,
        idempotency_key: str,
        collection: str,
        evidence: dict,
        notes: list[str] | None = None,
        artifacts: list[str] | None = None,
        reason: str,
        actor: str,
    ):
        """Atomically append an idempotent external-effect receipt."""

        return self.store.append_ticket_evidence(
            ticket_id,
            idempotency_key=idempotency_key,
            collection=collection,
            evidence=evidence,
            notes=notes,
            artifacts=artifacts,
            reason=reason,
            actor=actor,
        )

    @staticmethod
    def _merge_model(current, model_cls, **changes):
        data = current.model_dump(mode="python", exclude_none=True) if current else {}
        for key, value in changes.items():
            if value is not None:
                data[key] = value
        return model_cls(**data)

    def claim_ticket(
        self,
        ticket_id: str,
        assigned_to: str | None = None,
        lease_seconds: int | None = None,
        *,
        reason: str | None = None,
        actor: str | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        lease_expires_at = None
        if lease_seconds:
            lease_expires_at = self._utcnow() + timedelta(seconds=lease_seconds)

        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            assigned_to=assigned_to or (ticket.execution.assigned_to if ticket.execution else None),
            lease_expires_at=lease_expires_at,
            state="ready" if (ticket.execution.state if ticket.execution else "pending") == "pending" else None,
        )
        return self.update_ticket(ticket_id, execution=execution, reason=reason, actor=actor)

    def start_ticket(self, ticket_id: str, assigned_to: str | None = None, *, reason: str | None = None, actor: str | None = None) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="running",
            assigned_to=assigned_to or (ticket.execution.assigned_to if ticket.execution else None),
            started_at=ticket.execution.started_at if ticket.execution and ticket.execution.started_at else self._utcnow(),
        )
        return self.update_ticket(ticket_id, status="in_progress", execution=execution, reason=reason, actor=actor)

    def complete_ticket(
        self,
        ticket_id: str,
        note: str | None = None,
        result=None,
        artifacts: list[str] | None = None,
        completion_receipt: dict | None = None,
        *,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        existing_notes = list(ticket.outputs.notes) if ticket.outputs else []
        existing_artifacts = list(ticket.outputs.artifacts) if ticket.outputs else []
        outputs = self._merge_model(
            ticket.outputs,
            TicketOutputs,
            notes=existing_notes + ([note] if note else []),
            artifacts=existing_artifacts + list(artifacts or []),
            result=result if result is not None else (ticket.outputs.result if ticket.outputs else None),
            completion_receipt=(
                completion_receipt
                if completion_receipt is not None
                else (ticket.outputs.completion_receipt if ticket.outputs else None)
            ),
        )
        execution_data = ticket.execution.model_dump(mode="python", exclude_none=False) if ticket.execution else {}
        execution_data.update(
            state="done",
            finished_at=self._utcnow(),
            lease_expires_at=None,
            last_error=None,
        )
        execution = TicketExecution(**execution_data)
        return self.update_ticket(
            ticket_id, status="done", execution=execution, outputs=outputs,
            reason=reason, actor=actor, expected_updated_at=expected_updated_at,
        )

    def fail_ticket(
        self,
        ticket_id: str,
        error: str,
        *,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        current_attempt = ticket.execution.attempt if ticket.execution else 0
        next_attempt = current_attempt + 1
        max_attempts = ticket.execution.max_attempts if ticket.execution else 1
        exhausted = next_attempt >= max_attempts
        execution_data = ticket.execution.model_dump(mode="python", exclude_none=False) if ticket.execution else {}
        execution_data.update(
            state="failed" if exhausted else "ready",
            finished_at=self._utcnow() if exhausted else None,
            lease_expires_at=None,
            assigned_to=None,
            attempt=next_attempt,
            last_error=error,
        )
        execution = TicketExecution(**execution_data)
        return self.update_ticket(
            ticket_id,
            status="failed" if exhausted else "open",
            execution=execution,
            reason=reason or error,
            actor=actor,
            expected_updated_at=expected_updated_at,
        )

    def block_ticket(self, ticket_id: str, reason: str | None = None, note: str | None = None, *, actor: str | None = None) -> Ticket | None:
        """Mark a ticket blocked and terminate any active execution claim.

        ``update_ticket(status="blocked")`` only changes the board status. For a ticket that was
        already started, that leaves ``execution.state="running"`` behind, which watchdogs read as
        an active but idle claim. Blocking is a lifecycle transition, so it must clear the running
        execution state too.
        The `reason` here is the block reason (used for description + history "reason").
        `actor` records who performed the block.
        """
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        data = ticket.execution.model_dump(mode="python", exclude_none=False) if ticket.execution else {}
        data.update({
            "state": "blocked",
            "assigned_to": None,
            "finished_at": self._utcnow(),
            "lease_expires_at": None,
        })
        updates: dict = {"status": "blocked", "execution": TicketExecution(**data)}
        if reason:
            updates["description"] = f"BLOCKED: {reason}"
            updates["reason"] = reason  # for history
        if note:
            updates["outputs"] = self._append_note(ticket, note)
        if actor:
            updates["actor"] = actor
        return self.update_ticket(ticket_id, **updates)

    def _append_note(self, ticket: Ticket, note: str) -> TicketOutputs:
        """Build an updated TicketOutputs with `note` appended to existing notes.

        Preserves existing artifacts and result. Shared by ready_ticket,
        wait_for_input and update_ticket --note (PLF-koru improvement #7).
        """
        existing_notes = list(ticket.outputs.notes) if ticket.outputs else []
        existing_artifacts = list(ticket.outputs.artifacts) if ticket.outputs else []
        return self._merge_model(
            ticket.outputs,
            TicketOutputs,
            notes=existing_notes + [note],
            artifacts=existing_artifacts,
            result=ticket.outputs.result if ticket.outputs else None,
        )

    def add_ticket_note(
        self,
        ticket_id: str,
        note: str,
        *,
        actor: str | None = None,
    ) -> Ticket | None:
        """Append a note without changing ticket or execution state."""

        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        normalized = note.strip()
        if not normalized:
            raise ValueError("ticket_note_required")
        return self.update_ticket(
            ticket_id,
            outputs=self._append_note(ticket, normalized),
            actor=actor,
        )

    def wait_for_input(
        self,
        ticket_id: str,
        prompt: str,
        env_keys: list[str] | None = None,
        note: str | None = None,
        *,
        reason: str | None = None,
        actor: str | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        existing_keys = list(ticket.inputs.env_keys) if ticket.inputs else []
        merged_keys = existing_keys + [key for key in (env_keys or []) if key not in existing_keys]
        inputs = self._merge_model(
            ticket.inputs,
            TicketInputs,
            prompt=prompt,
            env_keys=merged_keys,
        )
        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="waiting_input",
            lease_expires_at=None,
        )
        updates: dict = {"execution": execution, "inputs": inputs}
        if note:
            updates["outputs"] = self._append_note(ticket, note)
        return self.update_ticket(ticket_id, reason=reason, actor=actor, **updates)

    def ready_ticket(self, ticket_id: str, note: str | None = None, *, reason: str | None = None, actor: str | None = None) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        execution_data = (
            ticket.execution.model_dump(mode="python", exclude_none=False)
            if ticket.execution
            else {}
        )
        execution_data.update(
            {
                "state": "ready",
                "assigned_to": None,
                "started_at": None,
                "finished_at": None,
                "lease_expires_at": None,
                "last_error": None,
            }
        )
        updates: dict = {
            "status": "open",
            "execution": TicketExecution(**execution_data),
        }
        if note:
            updates["outputs"] = self._append_note(ticket, note)
        if reason:
            updates["reason"] = reason
        if actor:
            updates["actor"] = actor
        return self.update_ticket(ticket_id, **updates)

    def respond_ticket(
        self,
        ticket_id: str,
        note: str,
        next_state: str | None = "ready",
        *,
        actor: str | None = None,
        reason: str | None = None,
        delegate_to: str | None = None,
        delegate_kind: str | None = None,
    ) -> Ticket | None:
        """Persist a human response and atomically move the ticket to its next work state."""
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None
        response = note.strip()
        if not response:
            raise ValueError("ticket_response_required")
        if next_state not in {None, "ready", "in_progress"}:
            raise ValueError("ticket_response_state_invalid")
        delegate = delegate_to.strip() if delegate_to else None
        if delegate_kind is not None and delegate_kind not in {"human", "bot"}:
            raise ValueError("ticket_delegate_kind_invalid")

        execution_data = (
            ticket.execution.model_dump(mode="python", exclude_none=False)
            if ticket.execution
            else {}
        )
        status = ticket.status
        if next_state is None:
            pass
        elif next_state == "ready":
            execution_data.update({
                "state": "ready",
                "assigned_to": None,
                "lease_expires_at": None,
                "last_error": None,
            })
            status = "open"
        else:
            execution_data.update({
                "state": "running",
                "assigned_to": actor or execution_data.get("assigned_to"),
                "started_at": execution_data.get("started_at") or self._utcnow(),
                "finished_at": None,
                "lease_expires_at": None,
                "last_error": None,
            })
            status = "in_progress"

        executor = ticket.executor
        if delegate:
            delegation_actor = self.resolve_delegation_actor(delegate)
            if delegation_actor is None:
                raise ValueError(f"ticket_delegate_not_allowed:{delegate}")
            if delegate_kind is not None and delegate_kind != delegation_actor.kind:
                raise ValueError(f"ticket_delegate_kind_mismatch:{delegate}")
            execution_data["queue"] = delegation_actor.queue
            if next_state == "in_progress":
                execution_data["assigned_to"] = delegation_actor.id
            executor = TicketExecutor(
                kind=delegation_actor.kind,
                mode="interactive" if delegation_actor.kind == "human" else "automatic",
                handler=delegation_actor.id,
            )

        return self.update_ticket(
            ticket_id,
            status=status,
            execution=TicketExecution(**execution_data),
            executor=executor,
            outputs=self._append_note(ticket, response),
            reason=reason or "human_response",
            actor=actor,
        )

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a single ticket by ID. Returns True if deleted, False if not found."""
        return self.store.delete_ticket(ticket_id)

    def delete_tickets(self, ticket_ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple tickets by ID. Returns (deleted_ids, not_found_ids)."""
        return self.store.delete_tickets_bulk(ticket_ids)

    def create_tickets_bulk(
        self,
        tickets_data: list[dict],
        source: str | None = None,
        sprint: str = "current",
    ) -> list[Ticket]:
        """Validate and persist a bounded batch with one write per sprint/shard."""
        if len(tickets_data) > self.MAX_BULK_TICKETS:
            raise ValueError(
                f"bulk_ticket_limit_exceeded:{len(tickets_data)}:{self.MAX_BULK_TICKETS}"
            )
        if not tickets_data:
            return []
        with self.store.mutation_lock():
            ticket_ids = self.store._reserve_ids_unlocked(len(tickets_data))
            tickets = []
            for ticket_id, original in zip(ticket_ids, tickets_data):
                data = dict(original)
                data.pop("id", None)
                if source and "source" not in data:
                    data["source"] = {"tool": source}
                data.setdefault("sprint", sprint)
                tickets.append(Ticket(id=ticket_id, **data))
            return self.store._create_tickets_bulk_unlocked(tickets)

    @property
    def delivery_plans(self) -> DeliveryPlanRepository:
        """Return the durable, execution-inert delivery-plan repository."""

        return DeliveryPlanRepository(self.store)

    def materialize_delivery_plan(
        self,
        compiled_plan: dict,
        *,
        terminal_receipts: list[dict] | tuple[dict, ...] = (),
    ) -> dict:
        """Atomically materialize a Strategy DAG or recover its exact prior IDs."""

        return self.delivery_plans.materialize(
            compiled_plan,
            terminal_receipts=terminal_receipts,
        )

    def checkpoint_delivery_candidate(self, checkpoint: dict) -> dict:
        """Append one explicit, hash-bound continuation checkpoint."""

        return self.delivery_plans.record_checkpoint(checkpoint)

    def record_delivery_terminal_receipt(self, plan_id: str, receipt: dict) -> dict:
        """Deduplicate a protected terminal receipt and close its exact slice."""

        return self.delivery_plans.record_terminal_receipt(plan_id, receipt)

    def record_delivery_split(self, split: dict) -> dict:
        """Link a split-required parent to already materialized bounded children."""

        return self.delivery_plans.record_split(split)

    def resume_delivery_plan(self, plan_id: str) -> dict:
        """Read the deterministic continuation frontier without executing tools."""

        return self.delivery_plans.resume(plan_id)


def quick_ticket(name: str, tool: str = "unknown", **kwargs) -> Ticket:
    """One-liner ticket creation for tools."""
    pf = Planfile.auto_discover()
    source = TicketSource(tool=tool, context=kwargs.pop("context", {}))
    return pf.create_ticket(name=name, source=source, **kwargs)


__all__ = [
    # Models
    "Strategy", "StrategyV1", "StrategyV2",
    "Sprint", "Task", "TaskPattern", "TaskType",
    "ModelHints", "ModelTier", "ModelTierV2",
    "Goal", "QualityGate",
    # Tickets
    "Ticket", "TicketStatus", "TicketSource",
    "TicketExecutor", "TicketExecution", "TicketInputs", "TicketOutputs",
    "CompiledWorkPlanV1", "DeliveryCheckpointV1", "DeliveryPlanError",
    "DeliveryPlanRepository", "DeliveryPlanSplitV1", "TicketCandidateV1",
    "WorkPlanTerminalReceiptV1",
    # Store & API
    "PlanfileStore", "Planfile", "quick_ticket",
    # Executors (lazy loaded)
    "StrategyExecutor", "execute_strategy", "TaskResult", "LLMClient",
    "create_openai_client", "create_litellm_client",
    # Runner (lazy loaded)
    "load_valid_strategy", "run_strategy", "verify_strategy_post_execution",
    "sync_todo_checkboxes_from_planfile",
    "run_testql_validation",
    "build_testql_tickets",
    "upsert_testql_tickets",
    "sync_testql_tickets",
    "validate_planfile_tickets",
    # DSL
    "DSLParser", "DSLExecutor", "DSLResult",
]

# Lazy loading functions for executors
def __getattr__(name):
    """Lazy import executor modules when accessed."""
    if name in ["runner", "executor_standalone"]:
        import importlib
        return importlib.import_module(f"planfile.{name}")
    elif name in ["load_valid_strategy", "run_strategy", "verify_strategy_post_execution"]:
        from planfile.runner import (
            load_valid_strategy,
            run_strategy,
            verify_strategy_post_execution,
        )
        if name == "load_valid_strategy":
            return load_valid_strategy
        elif name == "run_strategy":
            return run_strategy
        else:
            return verify_strategy_post_execution
    elif name in ["StrategyExecutor", "execute_strategy", "TaskResult", "LLMClient",
                 "create_openai_client", "create_litellm_client"]:
        from planfile.executor_standalone import (
            LLMClient,
            StrategyExecutor,
            TaskResult,
            create_litellm_client,
            create_openai_client,
            execute_strategy,
        )
        if name == "StrategyExecutor":
            return StrategyExecutor
        elif name == "execute_strategy":
            return execute_strategy
        elif name == "TaskResult":
            return TaskResult
        elif name == "LLMClient":
            return LLMClient
        elif name == "create_openai_client":
            return create_openai_client
        else:
            return create_litellm_client
    raise AttributeError(f"module 'planfile' has no attribute '{name}'")
