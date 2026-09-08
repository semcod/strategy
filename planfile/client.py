"""Stable in-process client for Planfile ticket lifecycle operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from filelock import Timeout as FileLockTimeout
from pydantic import BaseModel, ConfigDict, Field

from planfile import Planfile
from planfile.core.models import Ticket

TICKET_TRANSITION_RESULT_SCHEMA_ID = "planfile.ticket-transition-result.v1"

TransitionCode = Literal[
    "ok",
    "ticket_not_found",
    "invalid_transition",
    "lock_timeout",
    "store_error",
]
TransitionOperation = Literal[
    "claim",
    "start",
    "complete",
    "fail",
    "ready",
    "block",
    "note",
]


class TicketTransitionResult(BaseModel):
    """Machine-readable lifecycle result; callers decide only from ``code``."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        strict=True,
    )

    schema_id: Literal["planfile.ticket-transition-result.v1"] = Field(
        default=TICKET_TRANSITION_RESULT_SCHEMA_ID,
        alias="schema",
    )
    operation: TransitionOperation
    code: TransitionCode
    retryable: bool = False
    attempts: int = Field(default=1, ge=1)
    ticket: dict[str, Any] | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.code == "ok"


class PlanfileClient:
    """Bounded SDK facade over :class:`planfile.Planfile`.

    Retry belongs here because it is a storage/transport concern. Scheduling,
    authorization and deciding whether a transition should happen remain with
    the caller (for example Koru).
    """

    def __init__(
        self,
        project_path: str = ".",
        *,
        backend: Planfile | None = None,
        lock_retry_attempts: int = 3,
        lock_retry_delay_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if lock_retry_attempts < 1:
            raise ValueError("lock_retry_attempts must be at least 1")
        if lock_retry_delay_seconds < 0:
            raise ValueError("lock_retry_delay_seconds cannot be negative")
        self._backend = backend or Planfile(project_path)
        self._lock_retry_attempts = lock_retry_attempts
        self._lock_retry_delay_seconds = lock_retry_delay_seconds
        self._sleep = sleep

    def next_ticket(
        self,
        sprint: str = "current",
        queue: str | None = None,
    ) -> Ticket | None:
        """Return the next ticket; selecting whether to execute it is caller policy."""

        return self._backend.next_ticket(sprint=sprint, queue=queue)

    def claim(
        self,
        ticket_id: str,
        *,
        assigned_to: str | None = None,
        lease_seconds: int | None = None,
    ) -> TicketTransitionResult:
        return self._apply(
            "claim",
            lambda: self._backend.claim_ticket(
                ticket_id,
                assigned_to=assigned_to,
                lease_seconds=lease_seconds,
            ),
        )

    def start(
        self,
        ticket_id: str,
        *,
        assigned_to: str | None = None,
        reason: str | None = None,
        actor: str | None = None,
    ) -> TicketTransitionResult:
        return self._apply(
            "start",
            lambda: self._backend.start_ticket(
                ticket_id,
                assigned_to=assigned_to,
                reason=reason,
                actor=actor,
            ),
        )

    def complete(
        self,
        ticket_id: str,
        *,
        note: str | None = None,
        result: Any = None,
        artifacts: list[str] | None = None,
        completion_receipt: dict[str, Any] | None = None,
        reason: str | None = None,
        actor: str | None = None,
    ) -> TicketTransitionResult:
        return self._apply(
            "complete",
            lambda: self._backend.complete_ticket(
                ticket_id,
                note=note,
                result=result,
                artifacts=artifacts,
                completion_receipt=completion_receipt,
                reason=reason,
                actor=actor,
            ),
        )

    def fail(
        self,
        ticket_id: str,
        *,
        error: str,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
    ) -> TicketTransitionResult:
        """Record one failed attempt, optionally only for an observed ticket revision."""

        return self._apply(
            "fail",
            lambda: self._backend.fail_ticket(
                ticket_id,
                error=error,
                reason=reason,
                actor=actor,
                expected_updated_at=expected_updated_at,
            ),
        )

    def ready(
        self,
        ticket_id: str,
        *,
        note: str | None = None,
        reason: str | None = None,
        actor: str | None = None,
    ) -> TicketTransitionResult:
        """Make a failed or waiting ticket runnable again for an explicit retry."""

        return self._apply(
            "ready",
            lambda: self._backend.ready_ticket(
                ticket_id,
                note=note,
                reason=reason,
                actor=actor,
            ),
        )

    def block(
        self,
        ticket_id: str,
        *,
        reason: str | None = None,
        note: str | None = None,
        actor: str | None = None,
    ) -> TicketTransitionResult:
        return self._apply(
            "block",
            lambda: self._backend.block_ticket(
                ticket_id,
                reason=reason,
                note=note,
                actor=actor,
            ),
        )

    def note(
        self,
        ticket_id: str,
        note: str,
        *,
        actor: str | None = None,
    ) -> TicketTransitionResult:
        return self._apply(
            "note",
            lambda: self._backend.add_ticket_note(ticket_id, note=note, actor=actor),
        )

    def _apply(
        self,
        operation: TransitionOperation,
        mutation: Callable[[], Any],
    ) -> TicketTransitionResult:
        for attempt in range(1, self._lock_retry_attempts + 1):
            try:
                ticket = mutation()
            except FileLockTimeout as exc:
                if attempt < self._lock_retry_attempts:
                    self._sleep(self._lock_retry_delay_seconds * attempt)
                    continue
                return TicketTransitionResult(
                    operation=operation,
                    code="lock_timeout",
                    retryable=True,
                    attempts=attempt,
                    error=str(exc),
                )
            except ValueError as exc:
                return TicketTransitionResult(
                    operation=operation,
                    code="invalid_transition",
                    attempts=attempt,
                    error=str(exc),
                )
            except OSError as exc:
                return TicketTransitionResult(
                    operation=operation,
                    code="store_error",
                    retryable=True,
                    attempts=attempt,
                    error=str(exc),
                )

            if ticket is None:
                return TicketTransitionResult(
                    operation=operation,
                    code="ticket_not_found",
                    attempts=attempt,
                )
            return TicketTransitionResult(
                operation=operation,
                code="ok",
                attempts=attempt,
                ticket=ticket.model_dump(mode="json"),
            )

        raise AssertionError("unreachable")


__all__ = [
    "PlanfileClient",
    "TICKET_TRANSITION_RESULT_SCHEMA_ID",
    "TicketTransitionResult",
    "TransitionCode",
    "TransitionOperation",
]
