now:

![Current Planfile web view](web/img_1.png)

before:

![Previous Planfile web view](web/img.png)

# Planfile

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![PyPI version](https://img.shields.io/pypi/v/planfile.svg)](https://pypi.org/project/planfile/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/planfile)](https://pypi.org/project/planfile/)
[![CI/CD](https://github.com/semcod/planfile/workflows/CI%2FCD%20with%20Auto%20Bug-Fix%20Loop/badge.svg)](https://github.com/semcod/planfile/actions)
[![Code Coverage](https://img.shields.io/codecov/c/github/semcod/planfile)](https://codecov.io/gh/semcod/planfile)
[![Code Quality](https://img.shields.io/badge/CC%CC%84-4.1-brightgreen)](https://github.com/semcod/planfile)
[![Functions](https://img.shields.io/badge/functions-395-blue)](https://github.com/semcod/planfile)
[![Modules](https://img.shields.io/badge/modules-56-blue)](https://github.com/semcod/planfile)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![MyPy](https://img.shields.io/badge/mypy-checked-blue)](https://mypy.readthedocs.io/)
[![Pydantic](https://img.shields.io/badge/pydantic-v2-blue)](https://pydantic.dev)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](https://strategy.readthedocs.io)
[![GitHub Issues](https://img.shields.io/github/issues/semcod/planfile)](https://github.com/semcod/planfile/issues)
[![GitHub Pull Requests](https://img.shields.io/github/issues-pr/semcod/planfile)](https://github.com/semcod/planfile/pulls)
[![GitHub Stars](https://img.shields.io/github/stars/semcod/planfile)](https://github.com/semcod/planfile/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/semcod/planfile)](https://github.com/semcod/planfile/network)
[![Last Commit](https://img.shields.io/github/last-commit/semcod/planfile)](https://github.com/semcod/planfile/commits/main)
[![Release Date](https://img.shields.io/github/release-date/semcod/planfile)](https://github.com/semcod/planfile/releases)
[![Project Status](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/semcod/planfile)


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.124-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$3.39-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-77.0h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $3.3933 (145 commits)
- 👤 **Human dev:** ~$7703 (77.0h @ $100/h, 30min dedup)

Generated on 2026-07-24 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

**Planfile** is an SDLC automation platform that provides strategic project management with CI/CD integration and automated bug-fix loops. It manages sprints and strategies across external ticket systems like GitHub, Jira, and GitLab.

## 📊 Project Metrics

- **56 modules** with **395 functions**
- **Cyclomatic Complexity**: CC̄=4.1 (improved from 4.2)
- **Critical functions**: 15 (target: ≤4)
- **Zero circular dependencies**
- **Languages**: Python (53), Shell (17), JavaScript (3)

## ✨ Features

- 🎯 **Strategy Modeling**: Define strategies and sprints in YAML with task patterns
- 🔄 **Automated CI/CD Loop**: Test → Ticket → Fix → Retest automation
- 🔌 **Multi-Backend Support**: Integrates with GitHub Issues, Jira, GitLab, and generic HTTP APIs
- 🤖 **LLM-Powered**: AI-driven bug reports and auto-fix capabilities
- 📊 **Progress Tracking**: Review strategy execution with detailed metrics
- 🚀 **CLI Tool**: Easy-to-use command-line interface for applying and reviewing strategies
- 🐍 **Python Library**: Use planfile programmatically in your Python applications
- 🌐 **REST API**: Run as FastAPI server for HTTP access and integrations
- 🎨 **Rich Output**: Beautiful terminal output with progress bars and tables
- 🐳 **Docker Support**: Containerized deployment with Ollama integration
- 🔧 **Extensible**: Easy to add new backends and custom integrations
- 🔍 **Code Analysis**: Integration with external tools (code2llm, vallm, redup)
- 🌐 **MCP Server**: Model Context Protocol server integration
- 🤖 **LLX Integration**: Advanced code analysis and model selection
- 🌉 **Proxy Routing**: Smart model routing via Proxym API
- 📈 **Metrics-Driven**: Project metrics analysis for informed planning
- 🗣️ **DSL (Domain Specific Language)**: Natural language-like commands for planfile operations
- 🐛 **Bug-First Priority**: Automatic bug prioritization over features for quality assurance

Public integrations should use the versioned
[`TicketProposalV1` and `PlanfileClient` contracts](docs/PUBLIC_CONTRACTS.md)
instead of parsing CLI display text.

## Quick Install

```bash
# Basic installation
pip install planfile

# With all backend integrations
pip install planfile[all]

# Or with specific backends
pip install planfile[github,jira]
pip install planfile[gitlab]
```

### 1. Create a Strategy

Create a `strategy.yaml` file:

```yaml
name: "My Project Strategy"
project_type: "web"
domain: "fintech"
goal: "Launch a secure payment processing platform"

sprints:
  - id: 1
    name: "Core Infrastructure"
    length_days: 14
    objectives:
      - Set up project structure
      - Implement authentication
    tasks:
      - type: "feature"
        title: "Setup project structure"
        description: "Create basic project layout and configuration"
        estimate: 2
        priority: "high"

  - id: 2
    name: "Payment Processing"
    length_days: 21
    objectives:
      - Implement payment gateway
      - Add security measures
    tasks:
      - type: "feature"
        title: "Payment gateway integration"
        description: "Integrate with payment provider API"
        estimate: 5
        priority: "critical"
```

# GitHub
export GITHUB_TOKEN=your_token
export GITHUB_REPO=owner/repo

# Jira
export JIRA_URL=https://company.atlassian.net
export JIRA_EMAIL=your@email.com
export JIRA_TOKEN=your_token
export JIRA_PROJECT=PROJ

# GitLab
export GITLAB_TOKEN=your_token
export GITLAB_PROJECT_ID=123
```

# Run automated bug-fix loop
planfile auto loop \
  --strategy ./strategy.yaml \
  --project . \
  --backend github \
  --max-iterations 5 \
  --auto-fix

# Check CI status
planfile auto ci-status

# Review strategy progress
planfile strategy review \
  --strategy ./strategy.yaml \
  --project . \
  --backend github
```

## 🐛 Bug-First Priority System

Planfile automatically prioritizes bugs over features to ensure quality and stability:

### **Automatic Priority Ordering**
Tickets are sorted by:
1. **Priority Level**: critical > high > normal > low
2. **Bug Flag**: bugs come before features at the same priority level
3. **Creation Date**: older tickets first within the same category
4. **Ticket ID**: final tiebreaker

### **How It Works**
```python
# Example sorting behavior
Priority: critical
├── Bug tickets (sorted by creation date)
└── Feature tickets (sorted by creation date)

Priority: normal  
├── Bug tickets (sorted by creation date)
└── Feature tickets (sorted by creation date)
```

### **Label-Based Detection**
- Tickets with `bug` label are treated as bugs
- All other tickets are treated as features
- No manual configuration required

### **Integration with Koru**
- **Koru** auto-promotes bugs to higher priorities
- **Planfile** respects bug-first ordering in `next_ticket()`
- **Consistent behavior** across both systems
- **Seamless workflow** whether using koru or planfile directly

### **Benefits**
- 🔧 **Quality First**: Bugs fixed before new features
- ⚡ **Automatic Triage**: No manual priority adjustments needed
- 🎯 **Predictable Execution**: Consistent ordering across all operations
- 🛡️ **Stability Assurance**: Prevents feature development while bugs exist
- 🔄 **Unified System**: Works with koru's auto-promotion and auto-repair modes

### **Usage Example**
```python
from planfile import Planfile

pf = Planfile.auto_discover()
next_ticket = pf.next_ticket()

# Returns highest priority ticket, bugs first
# Critical bugs > Critical features > High bugs > High features > ...
```

## 🚦 Runnability Contract

`next_ticket()` returns the next **runnable** ticket, not merely the next *open* one. For an
autonomous queue (e.g. koru), "runnable" is the single source of truth for what may be handed to a
worker. A ticket is runnable only when **all** hold:

| Axis | Runnable when… |
|------|----------------|
| `status` | `open` |
| `execution.state` | `pending` / `ready` / unset |
| `blocked_by` | every dependency ticket is `done` / `canceled` |
| autonomy boundary | **no** `autonomy-frontier` label |
| human / resource wait | **no** `actor:human`, `needs-human:*`, or `waiting:*` label |
| goal focus | on the active `CURRENT_GOAL` (if the env var is set) |

**Why this exists:** `blocked_by` models a *ticket→ticket dependency*, but a human/resource wait
is a **label** (`waiting:node`, `actor:human`, …) — a distinct axis that must not be forced into
`blocked_by`. Without the runnability filter, `next_ticket()` kept re-serving the same un-doable
ticket (worker picks → can't execute → ticket reopened → picked again), so an autonomous loop
would churn on tickets it can never complete. The filter stops that at the source.

Inspect it with the debug view:

```bash
planfile ticket next --debug            # servable list + why each open ticket is skipped
planfile ticket next --debug --format json
```
```text
selected: IFURI-219
servable (3): IFURI-219, IFURI-220, IFURI-221
  IFURI-033 skipped: waiting:node
  IFURI-043 skipped: needs-human:pypi-token
  IFURI-199 skipped: blocked_by:IFURI-202
```

Programmatic access: `pf.runnability_skip_reason(ticket)` (→ `""` if runnable, else the reason) and
`pf.runnable_report()` (→ `{selected, servable, skipped:[{id, reason}]}`).

**Emergency bypass:** `PLANFILE_NO_AUTONOMY_FILTER=1` disables the autonomy/wait filter (frontier
and human tickets become servable again). Use only to diagnose; `--debug` surfaces a warning while
it is active. `CURRENT_GOAL` freeze is env-only by design — planfile never reads a runtime state
file, so the generic task store stays decoupled from any specific runtime.

### 4. Using Python Library

```python
from planfile import Planfile, quick_ticket

# Auto-discover .planfile/ in your project
pf = Planfile.auto_discover(".")

# Create tickets programmatically
ticket = pf.create_ticket(
    name="Fix authentication bug",
    description="Users cannot login with OAuth",
    priority="high",
    labels=["bug", "backend"]
)

# List and filter tickets
tickets = pf.list_tickets(sprint="current", status="open")

# Quick one-liner for tools
ticket = quick_ticket("Production alert", tool="monitoring", priority="critical")
```

# Start the FastAPI server
uvicorn planfile.api.server:app --reload --port 8000

# Use the API
curl "http://localhost:8000/tickets?sprint=current"
curl -X POST "http://localhost:8000/tickets" \
  -H "Content-Type: application/json" \
  -d '{"name": "API fix", "priority": "high"}'
```

### 5. Ticket Management CLI

Create, update, delete and bulk-manage tickets directly from command line:

```bash
# Create a new ticket
planfile ticket create "Fix login bug" -p high -l bug -l backend

# List tickets with filters
planfile ticket list --status open
planfile ticket list --label bug --format json

# Show the next runnable ticket in a queue-like workflow
planfile ticket next
planfile ticket next --format json

# Lifecycle for queue-driven execution
planfile ticket input PLF-001 --prompt "Provide OPENROUTER_API_KEY" --env-key OPENROUTER_API_KEY
planfile ticket ready PLF-001
planfile ticket claim PLF-001 --assigned-to koru-shell
planfile ticket start PLF-001 --assigned-to koru-shell
planfile ticket fail PLF-001 --error "HTTP 502 from upstream"
planfile ticket complete PLF-001 --note "Bootstrap done" --artifact reports/bootstrap.json

# Update a single ticket
planfile ticket update PLF-001 --status done
planfile ticket update PLF-002 --priority critical

# Validate if tickets are still current
planfile ticket validate
planfile ticket validate Q01 Q02 --issues analyses/issues.yaml --format yaml
planfile ticket validate --stale-only --fail-on-stale

# Delete tickets by ID
planfile ticket delete PLF-001 PLF-002

# Delete tickets matching filters (with confirmation)
planfile ticket delete --status done --force
planfile ticket delete --sprint old-sprint --label archive

# Preview deletions without executing
planfile ticket delete --label old --dry-run

# Bulk update tickets by filters
planfile ticket bulk-update --status-filter open --new-status in_progress
planfile ticket bulk-update --label todo --new-status done --force

# Change priority for all open bugs
planfile ticket bulk-update --status-filter open --label bug --new-priority high

# Add/remove labels in bulk
planfile ticket bulk-update --label old --add-label archived --remove-label old

# Move tickets between sprints
planfile ticket bulk-update --sprint current --status-filter done --move-to-sprint completed

# Combine multiple updates
planfile ticket bulk-update \
  --sprint sprint-1 \
  --status-filter open \
  --new-status in_progress \
  --new-priority high \
  --add-label urgent
```

#### Bounded ticket storage

Planfile automatically separates operational work from history. Terminal
`done`, `canceled`, `failed`, and `blocked` tickets move into daily
`.planfile/sprints/history-YYYY-MM-DD.yaml` files as soon as they become
terminal. The sweep also runs when the API starts and once per UTC day to catch
external file edits. If `current` exceeds 100
tickets or 1 MB, Planfile may also rotate older terminal work while keeping the
20 most recent terminal tickets. Active tickets are never archived. Ticket IDs
and history are preserved; use `sprint=all` only when a listing intentionally
needs history. Existing monthly `archive-YYYY-MM.yaml` files remain readable.
Planfile keeps a small locator in
`.planfile/index/history-locations.yaml`, so normal ticket lookups and stale
snapshot protection do not need to parse every history file.
See [Daily terminal history](docs/guides/DAILY_TERMINAL_HISTORY.md) for the
ordering and compatibility contract.

#### Public forensic event log

Every ticket mutation, evidence append, configuration decision, and persisted
management observation has a compact `PLOG/1` projection in
`.planfile/events/logs.dsl.txt`. Previous UTC days live in daily history files.
Applications and LLM tools can use the bounded public endpoints
`GET /logs.dsl.txt`, `GET /logs`, and `GET /logs/days`, with optional
`ticket_id`, `event_type`, `day`, and `limit` filters. PLOG keeps reasons,
actors, state transitions, decisions, correlation IDs, and SODL event hashes
readable while excluding large payloads. See
[Public forensic log DSL](docs/guides/FORENSIC_LOG_DSL.md) for the grammar,
retention layout, redaction, and API examples.

The defaults apply to existing projects without a configuration change. They
can be adjusted or disabled through the validated configuration interface (or
reviewed directly in `.planfile/config.yaml`):

```bash
planfile config set store.archive.max_current_tickets 500
planfile config set store.archive.enabled false --dry-run
planfile config set integrations.github.repo owner/project
```

```yaml
archive:
  enabled: true
  max_current_tickets: 100
  max_current_bytes: 1000000
  retain_terminal_tickets: 20
  retain_terminal_days: 0
  terminal_statuses: [done, canceled, failed, blocked]
```

`retain_terminal_days: 0` keeps `current` active-only. Set it to `1` to keep
terminal tickets from the current UTC date, or a larger number for a longer
operational review window.

For large or frequently mutated queues, Planfile also provides an opt-in
sharded YAML backend. It keeps the public ticket/API contract unchanged while
limiting a point update to one fixed ID-range file:

```bash
# Inspect the current backend and physical file count
planfile storage status

# Verified migration; legacy sprint files are retained in a recovery backup
planfile storage migrate --backend sharded-yaml --shard-size 100

# Build an optional, disposable SQLite index for fast summary pages and filters
planfile storage index-enable
planfile storage index-status

# The same transitions are available through portable DSL/OQL commands
planfile dsl run "set config store.storage.index=sqlite"
```

The resulting layout uses `.planfile/sprints/current.shards/metadata.yaml`,
`manifest.json`, and `tickets-000000-000099.yaml`-style files. IDs without a
numeric suffix use stable hash shards. See
[`docs/guides/TICKET_STORAGE_SCALING_PLAN.md`](docs/guides/TICKET_STORAGE_SCALING_PLAN.md)
for format choices, database options, consistency rules and benchmark targets.
SQLite stores a materialized projection only: YAML and JSONL remain authoritative,
and `planfile storage index-rebuild` recreates the database after manual edits or
cache corruption.

Set either limit to `0` to disable that limit, or set `enabled: false` to turn
automatic archiving off entirely.

### 6. Project Validation and Health

Use `validate schema` for machine-checkable plan files and sprint files. Sprint
YAML files should be validated explicitly with `--file-type sprint`; otherwise
auto-detection can treat them like root strategy files.

```bash
# Validate IFURI-style sprint files
planfile validate schema .planfile/sprints/current.yaml --file-type sprint
planfile validate schema .planfile/sprints/backlog.yaml --file-type sprint

# Validate the root strategy file
planfile validate schema planfile.yaml --file-type planfile

# Analyze a project and produce improvement tickets
planfile health check .
```

`ticket fail` records one failed execution by incrementing
`execution.attempt`, setting `execution.state: failed`, clearing the lease, and
persisting `execution.last_error`. It does not decide whether the work should
run again. The scheduler owns that policy: compare the new attempt count with
`execution.max_attempts`, then call `ticket ready` only when another run is
allowed. `ticket ready` reopens the ticket (`status: open`,
`execution.state: ready`) and clears stale assignment/timing fields while
preserving the attempt count.

Example retry sequence for a ticket with `max_attempts: 3`:

```bash
planfile ticket start PLF-001 --assigned-to worker-1
planfile ticket fail PLF-001 --error "HTTP 502 from upstream"  # attempt = 1
planfile ticket ready PLF-001 --note "Retry 2/3 scheduled"
```

Blocking is different from failure: use `ticket block` when progress requires
human input, approval, credentials, or another external state change. Do not
automatically reopen such operational boundaries.

`health check` accepts parser issues with the canonical `name` field and
normalizes generated ticket buckets before rendering, so project analysis works
for both list-based and priority-bucketed issue output. On large repositories,
`planfile health check .` performs a full scan and can take noticeably longer
than schema validation.

### 7. Queue-Oriented Execution Metadata

`planfile` tickets can also carry lightweight execution metadata for queue-like
workflows, which makes them a good control plane for tools like `koru`.

Common fields:

- `executor.kind` — who should perform the task: `human | shell | mcp | api | llm`
- `executor.mode` — `interactive` or `automatic`
- `executor.handler` — script, tool, or adapter name
- `execution.state` — `pending | ready | running | waiting_input | done | failed | skipped`
- `execution.attempt` — number of persisted failed executions
- `execution.max_attempts` — scheduler-owned ceiling for complete executor runs
- `inputs.*` — prompt, env keys, script path, API request, MCP tool, model hint
- `outputs.*` — artifacts, notes, structured result payload

Example:

```yaml
tickets:
  PLF-001:
    name: "Bootstrap OpenRouter integration"
    status: open
    priority: high
    executor:
      kind: shell
      mode: automatic
      handler: scripts/bootstrap.sh
    execution:
      queue: default
      state: ready
      max_attempts: 3
    inputs:
      env_keys:
        - OPENROUTER_API_KEY
      script: scripts/bootstrap.sh
      api_endpoint: null
      api_method: GET
      api_headers: {}
      api_body: null
      api_timeout_seconds: 30
    outputs:
      artifacts:
        - reports/bootstrap.json
```

For API-executed tasks, tools such as `koru` can use `executor.kind: api`
with `inputs.api_endpoint`, `inputs.api_method`, `inputs.api_headers`,
`inputs.api_body`, and `inputs.api_timeout_seconds`.

`planfile ticket next` returns the highest-priority runnable open ticket whose
dependencies in `blocked_by` are already `done` or `canceled`.

Execution changes are also broadcast to WebSocket clients connected to `/ws`.
This lets tools such as `koru` or a small dashboard watch the queue without
polling every endpoint.

External executors should record an already-committed side effect through the
atomic evidence endpoint instead of performing a client-side `GET` followed by
replacement of the complete `outputs` object:

```http
POST /tickets/PLF-001/evidence
Content-Type: application/json

{
  "idempotency_key": "smtp:message-123",
  "collection": "process_executions",
  "evidence": {"execution_id": "smtp:message-123", "status": "succeeded"},
  "artifacts": ["bridge-audit.jsonl#execution_id=smtp:message-123"],
  "actor": "mail-bridge",
  "reason": "Persist committed SMTP delivery evidence."
}
```

The idempotency key identifies the external effect, not the HTTP request. A
retry after a response timeout returns `deduplicated: true` and never appends a
second receipt. The response is a small acknowledgement; dashboard broadcast
is performed after it. Reusing a key with different evidence returns HTTP 409
`evidence_idempotency_conflict`.

Accepted receipts are stored as append-only events in
`.planfile/evidence/<ticket-id>.jsonl` and projected into `outputs` on every
single-ticket and list read. The sprint YAML remains the ticket snapshot, while
the evidence journal is the durable source for incremental external-effect
receipts. Backups must therefore include the complete `.planfile` directory.
This separation keeps each receipt write bounded even when `current.yaml` and a
long-running process ticket have grown to several megabytes.

### Closed delegation catalogue

The dashboard's **Delegate to actor / queue** control is populated from a JSON
catalogue, not from ticket history or free text. Set
`PLANFILE_DELEGATION_ACTORS_FILE` to a file with this shape:

```json
{
  "actors": [
    {"id": "operations-lead", "label": "Operations lead", "kind": "human"},
    {"id": "project-operator-bot", "label": "Project operator", "kind": "bot"}
  ]
}
```

`queue` defaults to `id`. Optional `principal` must equal `<kind>:<id>`.
Without a catalogue, delegation is disabled. `POST /tickets/{id}/respond`
returns HTTP 422 for an unknown actor or a mismatched actor kind, so bypassing
the browser select does not bypass the policy. `GET /delegation/actors`
returns the active catalogue.

Set `PLANFILE_ACCESS_PANEL_URL` to the public control-panel URL (or `auto`) and
`PLANFILE_ACCESS_PANEL_PORT` when the editor runs on a different port. Ticket
detail then shows **Manage actor permissions**, which opens the actor's AQL
contract editor, and **Delegation manager**, which opens role-based manual or
automatic routing. Delegating a ticket never expands the actor's contract.

Example event:

```json
{
  "type": "ticket.execution.changed",
  "action": "claim",
  "ticket_id": "PLF-001",
  "ticket": {
    "id": "PLF-001",
    "name": "Bootstrap OpenRouter integration",
    "execution": {
      "state": "ready",
      "assigned_to": "koru-shell"
    }
  }
}
```

**Auto-sync after changes:**
```bash
# Create ticket and sync immediately
planfile ticket create "Fix login bug" -p high --sync

# Delete tickets and auto-sync
planfile ticket delete --status done --sync

# Bulk update with sync
planfile ticket bulk-update --label bug --new-status done --sync

# Preview sync (dry-run)
planfile ticket update PLF-001 --status done --sync --sync-dry-run
```

### 6. Sync with External Systems

Synchronize tickets with TODO.md, OneDev, GitHub, Jira, and GitLab:

```bash
# Sync with markdown files (TODO.md, CHANGELOG.md)
planfile sync markdown

# Preview sync without making changes
planfile sync markdown --dry-run

# Sync only to external system (export)
planfile sync markdown --direction to

# Sync only from external system (import)
planfile sync markdown --direction from

# Sync with GitHub Issues (requires github.planfile.yaml config)
planfile sync github

# Use OneDev as the local queue
planfile sync onedev

# Import from OneDev and publish through Planfile to GitHub
planfile sync publish onedev github

# Sync with all configured integrations
planfile sync all

# Example: Export all done tickets to CHANGELOG.md
planfile ticket bulk-update --status-filter done --add-label changelog
planfile sync markdown --direction to --dry-run

# Watch .planfile/ directory and auto-sync on changes
planfile sync watch

# Watch with custom polling interval (seconds)
planfile sync watch --interval 10

# Watch specific integrations only
planfile sync watch --integration github --integration jira

# One-time sync (no watch loop)
planfile sync watch --once

# Watch with sync direction "from" (import from external systems)
planfile sync watch --direction from
```

**Sync Configuration:**

Create `github.planfile.yaml` for GitHub integration:
```yaml
integrations:
  github:
    repo: "owner/repo"
    token: "${GITHUB_TOKEN}"  # or auto-detected from `gh auth token`
```

For a local-first queue, create `onedev.planfile.yaml`:

```yaml
integrations:
  onedev:
    url: http://127.0.0.1:6610
    project: subactor/doctor-agent
    username: ${ONEDEV_USER}
    password_file: ${ONEDEV_PASSWORD_FILE}
    publish_to: [github]
  github:
    repo: subactor/doctor-agent
    token: ${GITHUB_TOKEN}
```

`publish_to` is routing metadata. OneDev and worker tools such as Koru do not
need GitHub Issue credentials: they write/read the OneDev queue, while
`planfile sync publish onedev github` owns publication. Backend-scoped IDs and
fingerprint markers prevent a OneDev Issue ID from being mistaken for a GitHub
Issue number and prevent duplicate publication after local state loss.

Markdown sync works out-of-the-box with `TODO.md` and `CHANGELOG.md` files.

To enable automatic checkbox syncing from `planfile.yaml` task statuses/results
in tools that reuse planfile APIs (e.g. `llx plan run`), add:

```yaml
integrations:
  markdown:
    sync_on_plan_run: true
    todo_file: TODO.md
```

### 7. DSL (Domain Specific Language)

Planfile includes a natural language-like DSL for quick operations:

```bash
# CLI DSL - single command
planfile dsl run "list tickets sprint=current status=open"
planfile dsl run 'create ticket "Fix login bug" priority=high'
planfile dsl run "update ticket PLF-001 status=done"
planfile dsl run "move ticket PLF-001 to sprint=2"
planfile dsl run "done ticket PLF-001"
planfile dsl run "list config"
planfile dsl run "set config store.archive.max_current_tickets=500"
planfile dsl run "validate"
planfile dsl run "sync github"

# CLI DSL - interactive shell
planfile dsl run
# Then type commands like:
# > list tickets sprint=current
# > create ticket "New task" priority=high
# > exit

# Format options
planfile dsl run "list tickets" --format json
planfile dsl run "list tickets" --format yaml
```

**Python API DSL:**

```python
from planfile import DSLExecutor

executor = DSLExecutor(project_path=".")
result = executor.run("list tickets sprint=current")
print(result.ok, result.data)

# Parser only
from planfile import DSLParser
parser = DSLParser()
cmd = parser.parse('create ticket "Fix bug" priority=high')
print(cmd.verb, cmd.target, cmd.params)
```

**REST API DSL:**

```bash
# Start server
uvicorn planfile.api.server:app --reload

# Execute DSL via HTTP
curl -X POST "http://localhost:8000/dsl" \
  -H "Content-Type: application/json" \
  -d '{"command": "list tickets", "project_path": "."}'

# WebSocket DSL
ws://localhost:8000/ws?project_path=.
```

**MCP DSL Tool:**

```bash
# Start MCP server
python -m planfile.mcp.server

# Mutating tools and DSL commands require an explicit operator capability.
PLANFILE_MCP_ALLOW_MUTATION=1 \
PLANFILE_MCP_PROJECT_ROOT=/path/to/projects \
python -m planfile.mcp.server

# MCP tool call (JSON-RPC)
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "planfile_dsl",
    "arguments": {
      "command": "list tickets sprint=current",
      "project_path": "."
    }
  }
}
```

Without `PLANFILE_MCP_ALLOW_MUTATION=1`, MCP only accepts the read-only DSL
verbs `get`, `help`, `list`, `query`, `show`, and `validate`, plus structured
read tools. Project paths are confined to the current directory unless
`PLANFILE_MCP_PROJECT_ROOT` selects a different trusted root.

**Supported DSL Commands:**
- `list tickets` — list with filters (sprint, status, priority, label)
- `create ticket` — create with name, priority, sprint, labels
- `show ticket` — show ticket by ID
- `update ticket` — update status, priority, name, labels
- `move ticket` — move to another sprint
- `done ticket` — mark as done
- `start ticket` — mark as in_progress
- `block ticket` — mark as blocked
- `delete ticket` — delete ticket
- `list sprints` — list all sprints
- `add sprint` — add new sprint
- `list config` / `show config PATH` — inspect effective redacted configuration
- `set config PATH=VALUE` — validate and apply an allowlisted configuration change
- `validate` — validate tickets
- `sync` — sync to integrations (github, jira, gitlab, all)
- `query` — query tickets with where clause
- `export` — export to formats (json, yaml, html)
- `help` — show command reference

Configuration commands share one typed contract across CLI, Python, REST,
WebSocket and MCP. Storage backend and index changes invoke their real
migration/build operations. Non-secret integration settings use a deterministic
OQL overlay; allocator state and secrets are not writable. Configuration
revisions and REST ETags protect against concurrent lost updates. See
[`docs/guides/OQL_CONFIGURATION.md`](docs/guides/OQL_CONFIGURATION.md) for the
coverage matrix, safety rules and examples for every entry point.

**Aliases:** add/new → create, ls → list, get/show → show, set/edit/patch → update, mv → move, finish/complete → done, begin → start

# Run CI loop with strategy
make ci-loop STRATEGY=strategy.yaml BACKENDS=github MAX_ITERATIONS=5

# Run examples
make example-github
make example-jira

# Full pipeline
make pipeline-docker
```

## 🔄 CI/CD Automation

Planfile provides complete automation for the bug-fix lifecycle:

1. **Test Execution**: Run your test suite
2. **Bug Detection**: Identify failing tests and code issues
3. **AI Analysis**: Generate detailed bug reports using LLM
4. **Ticket Creation**: Create tickets in your PM system
5. **Auto-Fix**: Optionally fix bugs automatically with AI
6. **Verification**: Re-run tests to verify fixes
7. **Loop**: Repeat until all tests pass

# Run with Docker Compose
docker-compose up -d

# Run auto-loop in container
docker-compose exec sprintstrat-runner planfile auto loop \
  --strategy /app/strategy.yaml \
  --project /workspace \
  --backend github \
  --max-iterations 5
```

## 📚 Documentation

- [Documentation Navigation](docs/NAVIGATION.md)
- [CI/CD Integration Guide](docs/CI_CD_INTEGRATION.md)
- [API Reference](docs/API.md)
- [CLI Reference](docs/CLI.md)
- [Examples](examples/)
- [Architecture Overview](docs/summaries/)
- [Migration Guide](docs/guides/MIGRATION_GUIDE.md)
- [Performance Guide](docs/guides/PERFORMANCE.md)
- [Examples Runner Guide](docs/guides/README_EXAMPLES.md)
- [Standalone Usage Guide](docs/guides/README_STANDALONE.md)
- [Changelog](CHANGELOG.md)

### Strategy Schema (v2)

The `strategy.yaml` file supports:

- **Sprints**: Time-boxed development periods with embedded tasks
- **Goals**: Project objectives with success criteria
- **Quality Gates**: Definition of done criteria
- **Model Hints**: AI model suggestions for different phases

### Example Strategy (v2)

```yaml
name: "My Project Strategy"
project_type: "web"
domain: "fintech"
goal:
  title: "Launch secure payment platform"
  description: "Build and deploy a secure payment processing system"
  success_metrics:
    - "99.9% uptime"
    - "<100ms response time"

sprints:
  - id: 1
    name: "Core Infrastructure"
    length_days: 14
    objectives: ["Set up project structure", "Implement authentication"]
    tasks:
      - type: "feature"
        title: "Setup project structure"
        description: "Create basic project layout and configuration"
        estimate: 2
        priority: "high"
        model_hints:
          small: "gpt-5.4-mini"
          large: "gpt-4o"

quality_gates:
  - name: "Code Coverage"
    criteria: ["coverage >= 80%"]
    required: true
```

### Backend Configuration

Each backend requires specific configuration:

```yaml
# GitHub backend
github:
  token: ${GITHUB_TOKEN}
  repo: ${GITHUB_REPO}

# Jira backend
jira:
  url: ${JIRA_URL}
  email: ${JIRA_EMAIL}
  token: ${JIRA_TOKEN}
  project: ${JIRA_PROJECT}
```

## 🤖 AI Integration

Planfile integrates with multiple LLM services:

- **Multiple Providers**: OpenAI, Anthropic, LiteLLM, Local LLMs
- **Smart Routing**: Automatic model selection via Proxym proxy
- **Code Analysis**: LLX integration for advanced metrics
- **Auto-Fix**: Automatic code generation for bug fixes
- **Strategy Generation**: AI-powered strategy creation

```bash
# Enable AI features
export OPENAI_API_KEY=your_key
export ANTHROPIC_API_KEY=your_key
export PROXY_API_URL=http://localhost:9999

# Run with auto-fix
planfile auto loop --strategy strategy.yaml --auto-fix

# Generate strategy with AI
planfile strategy generate ./my-project --model gpt-4o
```

## 📚 Examples

Explore the `examples/` directory for comprehensive use cases:

# List all available examples
planfile examples list

# Run a specific example
planfile examples run code2llm

# Run all examples (with timeout protection)
planfile examples run --all
```

### Featured Examples

- **[checkbox-tickets](examples/checkbox-tickets/)** - Native markdown checkbox support (`- [ ]` / `- [x]`)
- **[code2llm](examples/code2llm/)** - Code analysis with LLM integration
- **[bash-generation](examples/bash-generation/)** - Generate bash scripts from strategies
- **[cli-commands](examples/cli-commands/)** - CLI usage patterns
- **[advanced-usage](examples/advanced-usage/)** - CI/CD integration examples
- **[interactive-tests](examples/interactive-tests/)** - Interactive mode demonstrations
- **[ecosystem](examples/ecosystem/)** - MCP, LLX, and proxy routing integrations
- **[cli](examples/cli/)** - DSL command-line interface examples
- **[mcp](examples/mcp/)** - MCP DSL tool integration
- **[python-api](examples/python-api/)** - Python API DSL usage
- **[rest-api](examples/rest-api/)** - REST API and WebSocket DSL

# examples/quick-start.yaml
name: "Quick Start Demo"
project_type: "web"
domain: "demo"
goal: "Demonstrate planfile capabilities"

sprints:
  - id: 1
    name: "Setup"
    length_days: 7
    tasks:
      - type: "feature"
        title: "Initialize project"
        description: "Create basic project structure"
        estimate: 1
        priority: "high"
```

For more examples, see the [examples directory](examples/).

### Web Project Strategy

```yaml
name: "E-commerce MVP"
project_type: "web"
domain: "ecommerce"
goal: "Launch minimum viable e-commerce platform"

sprints:
  - id: 1
    name: "Foundation"
    length_days: 10
    tasks:
      - type: "feature"
        title: "Setup project structure"
        estimate: 1
      - type: "feature"
        title: "Database schema"
        estimate: 3
```

### Mobile App Strategy

```yaml
name: "Mobile App MVP"
project_type: "mobile"
domain: "healthcare"
goal: "Launch health tracking mobile app"

sprints:
  - id: 1
    name: "Core Features"
    length_days: 14
    tasks:
      - type: "feature"
        title: "User authentication"
        estimate: 3
      - type: "feature"
        title: "Health data tracking"
        estimate: 5
```

### Version Control

- **GitHub**: Issues, Projects, Actions
- **GitLab**: Issues, CI/CD, Merge Requests
- **Bitbucket**: Issues, Pipelines

### Project Management

- **Jira**: Issues, Epics, Sprints
- **Linear**: Issues, Projects, Teams
- **ClickUp**: Tasks, Lists, Spaces
- **Asana**: Tasks, Projects, Portfolios

### CI/CD Platforms

- **GitHub Actions**: Workflow automation
- **GitLab CI**: Pipeline integration
- **Jenkins**: Build automation
- **Azure DevOps**: Release management

# Clone repository
git clone https://github.com/semcod/planfile
cd strategy

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run linting
ruff check src/ tests/
ruff format src/ tests/

# Run complete test suite (REST, WebSockets, MCP, CLI, DSL)
pytest
```

### 🌐 API, WebSocket & MCP Architecture

Planfile is built with standard, production-ready interfaces for both humans and AI agents:

1. **REST API**: A robust, fully typed **FastAPI** server exposing comprehensive endpoints for managing tickets, sprints, and system configurations.
   * Start with: `uvicorn planfile.api.server:app --reload`
   * API endpoints cover: ticket lifecycle (claim, start, complete, fail), event ingestion, and live configurations.

2. **WebSockets (WS)**: High-performance bidirectional connection manager under `/ws`.
   * Automatically broadcasts ticket execution changes (`ticket.execution.changed`) and ticket updates (`ticket.changed`) in real-time.
   * Supports executing DSL commands dynamically in-session.

3. **MCP Server**: Implements the official **Model Context Protocol (MCP)** (version `2024-11-05`) via standard JSON-RPC over `stdio`.
   * Start with: `python -m planfile.mcp.server`
   * Registers various tools like `planfile_dsl`, `planfile_list_tickets`, `planfile_yaml_get`, and `planfile_yaml_patch` to allow LLM agents to orchestrate files and tickets directly.

4. **Testing Coverage & Parallel Execution**:
   * All API, WebSocket lifecycle events, and state mutations are thoroughly tested.
   * `tests/test_ticket_api_events.py` verifies FastAPI routes, WebSocket broadcasts, event histories, and queue dashboards.
   * `tests/test_mcp_server.py` tests JSON-RPC Handlers, stdio lifecycle, and YAML-patch operations of the Model Context Protocol server.
   * **Parallel Testing**: Supports running test suites in parallel using `pytest -n auto` (via `pytest-xdist`). Configured with a fallback-safe shell executor command to automatically execute sequentially if `pytest-xdist` is not installed, preventing pipeline crashes.

5. **LibYAML High-Performance C-Bindings**:
   * The file-based ticket store utilizes LibYAML's fast C-extensions (`CSafeLoader` and `CDumper`) when available, resulting in **up to 50x faster** load, write, and bulk-update speeds. Automatically falls back gracefully to pure Python implementations if C-bindings are not present.

### Project Structure

```
planfile/
├── planfile/              # Main package
│   ├── analysis/          # Code analysis components
│   │   ├── external_tools.py    # External tool integrations
│   │   ├── generator.py         # Strategy generation
│   │   ├── file_analyzer.py     # File analysis
│   │   ├── sprint_generator.py  # Sprint generation
│   │   ├── parsers/             # YAML/JSON/Toon parsers
│   │   └── generators/          # Metrics extractors
│   ├── cli/               # CLI commands
│   │   ├── cmd/           # Core commands (init, generate, apply, etc.)
│   │   ├── auto_loop.py   # CI/CD automation
│   │   └── extra_commands.py # Additional utilities
│   ├── integrations/      # Backend integrations
│   │   ├── github.py      # GitHub Issues
│   │   ├── jira.py        # Jira
│   │   ├── gitlab.py      # GitLab
│   │   └── generic.py     # Generic HTTP API
│   ├── llm/               # LLM integrations
│   │   ├── adapters.py    # Multiple LLM adapters
│   │   ├── client.py      # LLM client
│   │   └── generator.py   # Strategy generation
│   ├── loaders/           # Data loaders
│   │   ├── yaml_loader.py # YAML loading/saving
│   │   └── cli_loader.py  # JSON/Markdown export
│   ├── models.py          # Core data models
│   ├── models_v2.py       # Simplified models
│   ├── runner.py          # Strategy execution
│   ├── ci_runner.py       # CI/CD automation
│   └── executor_standalone.py # Standalone executor
├── examples/              # Usage examples
│   ├── quick-start/       # Basic examples
│   ├── ecosystem/         # Integration examples
│   └── advanced-usage/    # Advanced features
├── tests/                 # Test suite
├── docs/                  # Documentation
└── project/               # Project analysis output
```

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📞 Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/semcod/planfile/issues)
- 💬 [Discussions](https://github.com/semcod/planfile/discussions)

## 🏆 Acknowledgments

- Built with [Typer](https://typer.tiangolo.com/) for CLI
- Styled with [Rich](https://rich.readthedocs.io/) for terminal output
- Validated with [Pydantic](https://pydantic-docs.helpmanual.io/) for data models

---

**Planfile** - Your strategic partner in SDLC automation. 🚀

## License

Licensed under Apache-2.0.
## Status

_Last updated by [taskill](https://github.com/oqlos/taskill) at 2026-04-25 13:42 UTC_

| Metric | Value |
|---|---|
| HEAD | `f7a4f3c` |
| Coverage | — |
| Failing tests | — |
| Commits in last cycle | 50 |

> Introduces a configuration management system across goal, examples, and docs; refactors and extends the code analysis engine and test suite to improve coverage. Includes documentation fixes (markdown output), a fix for code quality metrics, and cleanup removing large generated files.

<!-- taskill:status:end -->

<!-- taskill:status:start -->

## Status

_Last updated by [taskill](https://github.com/oqlos/taskill) at 2026-04-25 18:22 UTC_

| Metric | Value |
|---|---|
| HEAD | `849565a` |
| Coverage | — |
| Failing tests | — |
| Commits in last cycle | 9 |

> Implemented a comprehensive configuration management system and CLI interface for the planfile project, including new command groups for backlog, sync, ticket, and validate operations.

<!-- taskill:status:end -->

## Dependency maintenance

See [internal dependency updates](docs/dependencies.md) for daily updates, locked tests and Python support.
