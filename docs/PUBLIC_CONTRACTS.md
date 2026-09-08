# Public automation contracts

Planfile exposes versioned Python contracts for analyzers and autonomous
orchestrators. These contracts separate a tool's proposal from the authority to
create, schedule or execute a ticket.

## Ticket proposal v1

`planfile.contracts.TicketProposalV1` is a strict, side-effect-free proposal.
Unknown fields are rejected. In particular it has no queue, sprint, executor,
capability, approval, transport or URI field.

```python
from planfile.contracts import TicketProposalV1

proposal = TicketProposalV1.model_validate({
    "schema": "planfile.ticket-proposal.v1",
    "proposal_id": "code2llm:src/service.py:Service",
    "dedupe_key": "symbol:src/service.py:Service",
    "name": "Split Service responsibilities",
    "priority": "high",
    "source": {
        "tool": "code2llm",
        "tool_version": "0.9.0",
        "finding_id": "src/service.py:Service",
    },
    "files": ["src/service.py"],
    "acceptance_criteria": ["Focused tests pass"],
})

canonical_payload = proposal.canonical_json()
proposal_hash = proposal.proposal_hash
safe_ticket_fields = proposal.to_ticket_kwargs()
```

Set-like fields are stripped, deduplicated and sorted before hashing. Ordered
acceptance criteria are stripped and deduplicated without changing their order.
The consumer remains responsible for deduplication, queue selection and
authorization before passing the safe fields to `Planfile.create_ticket`.

The JSON Schema for non-Python producers can be obtained from
`TicketProposalV1.model_json_schema(by_alias=True)`.

## Ticket lifecycle result v1

`planfile.client.PlanfileClient` wraps lifecycle mutations and returns
`TicketTransitionResult` with a stable code:

- `ok`
- `ticket_not_found`
- `invalid_transition`
- `lock_timeout`
- `store_error`

```python
from planfile.client import PlanfileClient

client = PlanfileClient("/workspace/project")
result = client.start("PLF-42", assigned_to="koru", actor="koru")
if result.code == "ok":
    ticket = result.ticket
elif result.retryable:
    schedule_retry(result.code)
```

Lifecycle methods are:

- `claim` and `start` for ownership and execution start;
- `complete` for verified success;
- `fail` for recording one failed attempt and its error;
- `ready` for an explicit scheduler decision to reopen work;
- `block` for a human or external-state boundary;
- `note` for additive evidence.

`fail` and `ready` are deliberately separate. Planfile persists state; it does
not assume that every error is retryable:

```python
failed = client.fail("PLF-42", error="temporary upstream failure", actor="koru")
ticket = failed.ticket or {}
execution = ticket.get("execution") or {}

if failed.code == "ok" and execution.get("attempt", 0) < execution.get("max_attempts", 1):
    reopened = client.ready(
        "PLF-42",
        note="Retry scheduled by koru",
        actor="koru",
    )
else:
    blocked = client.block("PLF-42", reason="attempt budget exhausted", actor="koru")
```

`ready` preserves the failure count but clears stale execution ownership,
timestamps, lease, and last error. Its returned ticket is runnable again with
`status: open` and `execution.state: ready`.

The client owns the bounded storage-lock retry. The caller owns the decision to
perform a transition, its capability/grant checks and its retry budget outside
the storage transport.

Compatibility policy: add a new version instead of weakening strict validation
or changing the meaning of an existing result code.

## Resumable delivery-plan DAG v1

`Planfile.materialize_delivery_plan` accepts the closed, execution-inert
`subactor.compiled-work-plan/v1` DTO emitted by Strategy. It atomically assigns
stable Planfile ticket IDs to its candidates and persists the runtime projection
under `.planfile/delivery-plans/<plan-id>.json`. Replaying the same DTO returns
the same IDs; if power fails after the ticket batch lands but before the state
replace, the exact candidate hash bindings recover that batch without creating
duplicates.

```python
state = planfile.materialize_delivery_plan(compiled_plan)
state = planfile.checkpoint_delivery_candidate(checkpoint_v1)
state = planfile.record_delivery_split(split_v1)
state = planfile.record_delivery_terminal_receipt(plan_id, terminal_receipt_v1)
frontier = planfile.resume_delivery_plan(plan_id)
```

Checkpoints have an explicit sequence and phase and bind the plan hash,
candidate digest and evidence references. Splits bind a `split_required` parent
to at least two already-materialized bounded children and rewire its dependents.
Terminal receipts are immutable and deduplicated by their complete protected
binding. A conflicting checkpoint, receipt, plan revision or candidate digest
fails closed.

The returned resume frontier is a deterministic projection of those structured
records. Planfile does not infer completion from chat prose and the contracts
reject command, executor, grant and tool-authority fields. Materialization
creates tickets with `executor=None`; selecting an agent or executing tools
remains a separate authorized runtime concern.

The persisted format is published as
`planfile/schemas/delivery-plan-state.schema.v1.json`. The state file and its
ticket YAML/event journals are authoritative continuity data and must be backed
up together; disposable SQLite and fast-JSON indexes are not substitutes.

## Atomic external evidence append

`POST /tickets/{ticket_id}/evidence` is the retry-safe write contract for an
external effect that has already happened. It atomically appends one evidence
event, notes and artifact references under the ticket store lock. The event is
durable in `.planfile/evidence/<ticket-id>.jsonl` and is projected into the
ticket's `outputs` on every read; the endpoint does not rewrite the complete
sprint snapshot. The required `idempotency_key` is persisted with the evidence
and suppresses duplicates when a caller retries after an ambiguous transport
timeout.

The same key and the same evidence is a successful deduplicated retry. The same
key with different evidence is rejected with HTTP 409
`evidence_idempotency_conflict`; accepted receipts are immutable.

Callers must not use generic `PATCH /tickets/{ticket_id}` with a previously read
`outputs` object for this purpose: that read/modify/write sequence can overwrite
evidence written concurrently by another executor.

The evidence journal and sprint YAML are complementary durable sources and must
be backed up together as the `.planfile` directory. A projection cache or JSON
mirror may be deleted and rebuilt; an evidence journal must not be discarded.
