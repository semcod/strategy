# Changelog

## [Unreleased]

### Fixed
- Normalized runtime `date`, `datetime` and `time` values at the final JSON
  mirror write boundary. Ticket mutations can no longer disable the sprint
  mirror and force every agent request to reparse the full YAML archive.
- Preserved management-event actor, correlation, causation, receipt, reason,
  decision, outcome, error, and idempotency context across `/events/ingest`,
  canonical SODL and the bounded public PLOG/1 projection.
- Stopped CI from publishing an unused `gh-pages` branch; GitHub Pages already
  serves the configured `main:/` source, so successful runs retain one branch.
- Pinned checkout, Python setup, cache and artifact upload to immutable official
  Node 24 Action revisions, removing runner deprecation compatibility mode.
- Serialized stale SQLite index rebuilds across readers and serve full and
  operational ticket lists directly from the index, avoiding concurrent archive
  materialization, SQLite reset races, and multi-gigabyte model caches.
- Evict superseded signature versions of the same ticket-list response so a
  frequently changing full-history query retains one serialized body, not four.

### Added
- Added a durable `planfile.delivery-plan-state/v1` runtime for materializing
  Strategy's inert ticket DAG, preserving parent/child split links, explicit
  continuation checkpoints and deduplicated protected terminal receipts. The
  resume projection survives a missing final state replace by recovering exact
  candidate ticket IDs, and never derives lifecycle state from chat prose.
- Added a public, append-only `PLOG/1` forensic timeline in
  `.planfile/events/logs.dsl.txt`, daily history partitions, bounded text/JSON
  APIs, streaming backfill from SODL, and durable coverage for evidence and
  management decisions. The compact projection keeps time, type, actor,
  reason, lifecycle logic and correlation data directly readable by LLMs.
- Added atomic `POST /tickets/{ticket_id}/evidence` for idempotent external-effect
  receipts. Retries after an ambiguous HTTP timeout now deduplicate under the
  store lock instead of requiring callers to replace the complete ticket output.
  Receipts are durably appended to a per-ticket event journal and projected into
  every ticket read, so recording evidence no longer rewrites a multi-megabyte
  sprint snapshot or times out late in a long process.
- Added a first-class OneDev Issues backend with CRUD, state transitions,
  fingerprint deduplication and full evidence import.
- Added public `OneDevBackend.ensure_project()` and `ensure_ticket()` contracts
  so local agents can reuse Planfile instead of maintaining another REST client.
- Added `planfile sync onedev` and `planfile sync publish SOURCE TARGET...` for
  local-first ticket queues with Planfile-owned GitHub publication.

### Changed
- Sync references are backend-scoped, preventing a OneDev issue ID from being
  reused accidentally as a GitHub issue number.
- Imported tickets preserve title, description, URL, metadata and configured
  `publish_to` routes.
- GitHub publication reuses both Planfile and legacy Doctor fingerprint markers.

### Fixed
- Kept the operational `current` sprint active-only by moving terminal tickets
  into `history-YYYY-MM-DD` files immediately by default. Added startup/daily
  maintenance, a lightweight history locator for bounded lookups, and stale
  snapshot protection so archived tickets cannot be resurrected by bulk sync.
- Bounded worker memory by excluding YAML snapshots larger than 5 MB, including
  legacy monthly archives, from parsed-data and ticket-model caches while
  keeping those files readable on demand.
- Made full-history list reads explicit: `sprint=all` without a declared `view`
  now returns the bounded current summary, preventing legacy service clients
  from repeatedly materializing the complete archive.
- Fixed `planfile serve` install hint: Rich no longer swallows `[api]` as
  console markup, so the error now prints the correct
  `pip install 'planfile[api]'` instead of an extras-less command.
- Silenced the `PytestCollectionWarning` for `TestResult` by marking the
  dataclass with `__test__ = False`; removed a dead `sys` import in the serve
  command.
- Fixed `planfile health check` so generated parser issues use the canonical
  `name` field and priority-bucketed ticket output is flattened before
  rendering.
- Documented explicit sprint validation with
  `planfile validate schema .planfile/sprints/current.yaml --file-type sprint`
  for roadmap-driven projects such as IFURI.
- Added pytest `pythonpath` configuration so local checkout tests import the
  editable package consistently.

### Changed
- chore(repo): move root guides to docs/guides (MIGRATION_GUIDE, PERFORMANCE, README_EXAMPLES, README_STANDALONE)
- chore(repo): move REFACTOR_CLI to docs/summaries
- chore(repo): move mcp-server-example to examples/ecosystem and planfile_gen to scripts/
- docs: add docs/NAVIGATION.md and refresh README documentation links
- chore(todo): keep `TODO.md` limited to active work from the 2026-05-03
  prefact snapshot (487 reported, 178 unresolved entries retained from the
  displayed slice); migrate its 22 resolved findings into release history
  instead of retaining completed checkboxes or duplicate open entries
- docs(todo): move the four completed manual-maintenance items into the
  `Fixed` section above and document the active-only tracking policy
- feat(goal): configuration management system
- feat(examples): configuration management system
- feat(docs): configuration management system
- feat(docs): code analysis engine
- refactor(docs): code analysis engine
- refactor(examples): code analysis engine
- feat(tests): added tests to improve coverage
- feat(tests): deep code analysis engine with 4 supporting modules
- fix(docs): add markdown output
- fix(planfile): code quality metrics with 3 supporting modules
- fix: remove large generated files from repository
- chore: pyqual auto-commit [skip ci]
- feat: added configuration management system with CLI interface
- feat: implemented backlog, sync, ticket, and validate command groups
- feat: added configuration management tests
- refactor: reorganized goal and config modules
- docs: updated documentation for configuration management system

## [0.1.123] - 2026-07-24

### Docs
- Update README.md
- Update docs/CLI.md
- Update docs/guides/OQL_CONFIGURATION.md
- Update docs/guides/TICKET_STORAGE_SCALING_PLAN.md

### Test
- Update tests/test_next_ticket_autonomy_filter.py
- Update tests/test_oql_configuration.py
- Update tests/test_sharded_yaml_storage.py
- Update tests/test_sqlite_ticket_index.py

### Other
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/cli/commands.py
- Update planfile/cli/groups/config/__init__.py
- Update planfile/cli/groups/config/commands.py
- Update planfile/cli/groups/storage/__init__.py
- Update planfile/cli/groups/storage/commands.py
- Update planfile/core/configuration.py
- Update planfile/core/sharded_yaml.py
- Update planfile/core/sqlite_index.py
- ... and 8 more files

## [0.1.119] - 2026-07-21

### Docs
- Update CHANGELOG.md
- Update README.md
- Update TODO.md
- Update docs/NAVIGATION.md
- Update docs/PUBLIC_CONTRACTS.md
- Update docs/README.md

### Test
- Update tests/test_next_ticket_autonomy_filter.py
- Update tests/test_public_contracts.py
- Update tests/test_store_concurrency.py
- Update tests/test_ticket_api_events.py
- Update tests/test_ticket_execution.py

### Other
- Update VERSION
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/client.py
- Update planfile/core/models/base.py
- Update planfile/core/models/ticket.py
- Update planfile/core/store.py
- Update planfile/runtime_context.py
- Update uv.lock

## [0.1.118] - 2026-07-20

### Added
- `PlanfileClient` now exposes typed `fail` and `ready` lifecycle operations,
  allowing queue schedulers to record an attempt and explicitly reopen it
  without falling back to subprocess-only lifecycle mutations.

### Fixed
- `ready_ticket()` now reopens an explicitly retried ticket and clears its
  stale execution claim while preserving the recorded attempt count.

## [0.1.117] - 2026-07-20

### Added
- Added bounded automatic ticket archiving. Oversized `current.yaml` files move
  their oldest terminal tickets into monthly archive sprint files while keeping
  active and recently completed work in the current sprint.
- Added per-project archive limits for ticket count, file size, retained terminal
  tickets, terminal statuses, and disabling the feature.

### Changed
- Archive writes are atomic, lock-protected, retry-safe, and refresh the fast JSON
  mirrors used by long-running API processes.

## [0.1.116] - 2026-07-19

### Docs
- Update README.md
- Update docs/PUBLIC_CONTRACTS.md

### Test
- Update tests/test_public_contracts.py
- Update tests/test_ticket_api_events.py
- Update tests/test_ticket_execution.py

### Other
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/client.py
- Update planfile/contracts.py

## [0.1.115] - 2026-07-16

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/api/server.py
- Update uv.lock

## [0.1.114] - 2026-07-15

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py
- Update tests/test_ticket_execution.py

### Other
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/core/models/__init__.py
- Update planfile/core/models/ticket.py
- Update planfile/delegation.py
- Update uv.lock

## [0.1.113] - 2026-07-15

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py
- Update tests/test_ticket_execution.py

### Other
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update uv.lock

## [0.1.112] - 2026-07-15

### Docs
- Update README.md

### Test
- Update tests/test_github_projects.py

### Other
- Update planfile/sync/__init__.py
- Update planfile/sync/github_projects.py

## [0.1.111] - 2026-07-15

### Docs
- Update README.md

### Test
- Update tests/test_cli_help.py

### Other
- Update planfile/__main__.py

## [0.1.110] - 2026-07-15

### Docs
- Update CHANGELOG.md
- Update README.md

### Test
- Update tests/test_fastio.py
- Update tests/test_health_analysis.py

### Other
- Update planfile/ci.py
- Update planfile/cli/groups/health/commands.py
- Update planfile/cli/groups/serve/commands.py
- Update planfile/core/fastio.py
- Update planfile/core/store.py
- Update planfile/core/store_tickets.py

## [0.1.109] - 2026-07-07

### Docs
- Update README.md

### Test
- Update tests/test_decompose.py
- Update tests/test_next_ticket_autonomy_filter.py
- Update tests/test_semantic.py
- Update tests/test_ticket_next_json.py

### Other
- Update planfile/__init__.py
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/decompose.py
- Update planfile/core/semantic.py

## [0.1.108] - 2026-07-07

### Docs
- Update README.md

### Test
- Update tests/test_decompose.py

### Other
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/decompose.py
- Update planfile/core/models/ticket.py

## [0.1.107] - 2026-07-06

### Docs
- Update README.md

### Other
- Update .planfile/.store.lock
- Update .planfile/config.yaml
- Update .planfile/config.yaml.fast.json
- Update .planfile/sprints/backlog.yaml.fast.json
- Update .planfile/sprints/current.yaml
- Update .planfile/sprints/current.yaml.fast.json
- Update local.dev.txt

## [0.1.106] - 2026-07-03

### Docs
- Update README.md

## [0.1.105] - 2026-07-03

### Docs
- Update README.md

## [0.1.104] - 2026-06-29

### Docs
- Update README.md

### Test
- Update tests/test_health_analysis.py

## [0.1.10] - 2026-05-03

### Fixed
- Fix duplicate-imports issues (ticket-c2fde1d9)
- Fix sorted-imports issues (ticket-a3d599b0)
- Fix smart-return-type issues (ticket-58960d82)
- Fix import-section-separators issues (ticket-499dcd75)
- Fix duplicate-imports issues (ticket-b8ac123d)
- Fix magic-numbers issues (ticket-77115806)
- Fix sorted-imports issues (ticket-fb9faa8d)
- Fix import-section-separators issues (ticket-5b6013d7)
- Fix string-concat issues (ticket-11369df8)
- Fix magic-numbers issues (ticket-0643b0ac)
- Fix llm-generated-code issues (ticket-0f2241ce)
- Fix magic-numbers issues (ticket-435049ed)
- Fix magic-numbers issues (ticket-247dc79f)
- Fix sorted-imports issues (ticket-a299e4f0)
- Fix import-section-separators issues (ticket-2588f063)
- Fix string-concat issues (ticket-89cb0c8a)
- Fix magic-numbers issues (ticket-31e97a21)
- Fix string-concat issues (ticket-81e690a1)
- Fix magic-numbers issues (ticket-a6c3c7d5)
- Fix magic-numbers issues (ticket-e9ce6681)
- Fix string-concat issues (ticket-76fbb641)
- Fix magic-numbers issues (ticket-c9fc5dfe)
- Fix ai-boilerplate issues (ticket-1d5db6c6)
- Fix string-concat issues (ticket-7925c4a3)
- Fix magic-numbers issues (ticket-d6e6d90a)
- Fix sorted-imports issues (ticket-222286a8)
- Fix import-section-separators issues (ticket-56a17b4b)
- Fix unused-imports issues (ticket-1cd19983)
- Fix sorted-imports issues (ticket-6e55b295)
- Fix import-section-separators issues (ticket-ed4db60c)
- Fix smart-return-type issues (ticket-c9ea4bd6)
- Fix magic-numbers issues (ticket-1dd016af)
- Fix string-concat issues (ticket-e0e73559)
- Fix magic-numbers issues (ticket-da35452a)
- Fix llm-generated-code issues (ticket-aad6a1c3)
- Fix smart-return-type issues (ticket-ef2c99a5)
- Fix llm-hallucinations issues (ticket-ed42776e)
- Fix llm-generated-code issues (ticket-f19715ec)
- Fix unused-imports issues (ticket-8c79da0f)
- Fix unused-imports issues (ticket-05e790d1)
- Fix unused-imports issues (ticket-dd0422a1)
- Fix magic-numbers issues (ticket-cbcafce8)
- Fix sorted-imports issues (ticket-778db3c4)
- Fix smart-return-type issues (ticket-4408d5ba)
- Fix import-section-separators issues (ticket-0cba269d)
- Fix string-concat issues (ticket-e90809aa)
- Fix unused-imports issues (ticket-6af68e7b)
- Fix duplicate-imports issues (ticket-80dda13d)
- Fix sorted-imports issues (ticket-dec21fab)
- Fix import-section-separators issues (ticket-6bf8e27f)
- Fix string-concat issues (ticket-61aa351a)
- Fix magic-numbers issues (ticket-b63220b8)
- Fix unused-imports issues (ticket-b4e7e932)
- Fix string-concat issues (ticket-395289d1)
- Fix unused-imports issues (ticket-26f09cab)
- Fix smart-return-type issues (ticket-245e5770)
- Fix sorted-imports issues (ticket-92427171)
- Fix import-section-separators issues (ticket-f3c1f13c)
- Fix unused-imports issues (ticket-d5ed9dba)
- Fix sorted-imports issues (ticket-4fee1e34)
- Fix import-section-separators issues (ticket-8acce233)
- Fix unused-imports issues (ticket-8013258d)
- Fix duplicate-imports issues (ticket-ffdd7341)
- Fix sorted-imports issues (ticket-b7d976a6)
- Fix import-section-separators issues (ticket-dd6b7dc7)
- Fix unused-imports issues (ticket-42a4f6aa)
- Fix sorted-imports issues (ticket-5ec8ef63)
- Fix import-section-separators issues (ticket-a60a2dae)
- Fix unused-imports issues (ticket-1cc7763f)
- Fix duplicate-imports issues (ticket-7c156c88)
- Fix relative-imports issues (ticket-5b211a62)
- Fix unused-imports issues (ticket-ef977421)
- Fix unused-imports issues (ticket-1ecae3d9)
- Fix unused-imports issues (ticket-c08b31f2)
- Fix magic-numbers issues (ticket-36c5cc0f)
- Fix relative-imports issues (ticket-27b7e217)
- Fix string-concat issues (ticket-30e38c46)
- Fix unused-imports issues (ticket-15a2073e)
- Fix relative-imports issues (ticket-e5c5b177)
- Fix string-concat issues (ticket-b978cb2d)
- Fix unused-imports issues (ticket-c6a47ba4)
- Fix unused-imports issues (ticket-ef643685)
- Fix string-concat issues (ticket-3cb95755)
- Fix unused-imports issues (ticket-0b3184c7)
- Fix unused-imports issues (ticket-73b9087a)
- Fix magic-numbers issues (ticket-597fa693)
- Fix relative-imports issues (ticket-18b357db)
- Fix unused-imports issues (ticket-a3a32b96)
- Fix llm-generated-code issues (ticket-037bd51b)
- Fix sorted-imports issues (ticket-ff7f8eb7)
- Fix unused-imports issues (ticket-65a7b0ca)
- Fix relative-imports issues (ticket-2a1035ef)
- Fix sorted-imports issues (ticket-2a9b2d06)
- Fix custom-import-organization issues (ticket-281a09e5)
- Fix string-concat issues (ticket-37efb683)
- Fix unused-imports issues (ticket-428d4f9e)
- Fix relative-imports issues (ticket-e88867b9)
- Fix duplicate-imports issues (ticket-61b79902)
- Fix unused-imports issues (ticket-843a36c1)
- Fix magic-numbers issues (ticket-f06d9698)

## [0.1.103] - 2026-06-05

### Docs
- Update README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/cli/groups/apply/commands.py
- Update planfile/cli/groups/apply/utils.py
- Update planfile/sync/operations.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 11 more files

## [0.1.102] - 2026-05-24

### Docs
- Update README.md

### Other
- Update config/goal.yaml

## [0.1.101] - 2026-05-24

### Docs
- Update README.md

### Other
- Update config/goal.yaml
- Update planfile/core/store.py
- Update uv.lock

## [0.1.100] - 2026-05-24

### Docs
- Update README.md

### Test
- Update tests/test_mcp_server.py

### Other
- Update .planfile/sprints/current.yaml
- Update planfile/mcp/server.py
- Update uv.lock

## [0.1.99] - 2026-05-24

### Docs
- Update README.md

### Other
- Update planfile/core/store.py
- Update uv.lock

## [0.1.98] - 2026-05-24

### Docs
- Update README.md

### Test
- Update tests/test_cli_help.py

### Other
- Update planfile/__init__.py
- Update planfile/cli/commands.py
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/core/store.py
- Update uv.lock

## [0.1.97] - 2026-05-19

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/api/server.py
- Update uv.lock

## [0.1.96] - 2026-05-14

### Docs
- Update README.md

### Other
- Update planfile/cli/commands.py
- Update planfile/cli/groups/serve/__init__.py
- Update planfile/cli/groups/serve/commands.py
- Update uv.lock

## [0.1.95] - 2026-05-14

### Docs
- Update README.md

### Other
- Update VERSION
- Update planfile/__init__.py
- Update uv.lock

## [0.1.93] - 2026-05-10

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/core/store.py
- Update uv.lock

## [0.1.92] - 2026-05-10

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/api/server.py
- Update uv.lock

## [0.1.91] - 2026-05-10

### Docs
- Update README.md

### Other
- Update planfile/api/server.py
- Update uv.lock

## [0.1.90] - 2026-05-10

### Docs
- Update README.md

### Test
- Update tests/test_cli_json_output.py
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/api/server.py
- Update planfile/cli/groups/backlog/commands.py
- Update planfile/cli/groups/dsl/commands.py
- Update planfile/cli/groups/ticket/commands.py
- Update uv.lock

## [0.1.89] - 2026-05-10

### Docs
- Update README.md

### Test
- Update tests/test_ticket_api_events.py

### Other
- Update planfile/api/server.py
- Update uv.lock

## [0.1.88] - 2026-05-10

### Docs
- Update README.md
- Update examples/c2004-healing/README.md

### Test
- Update tests/test_ticket_api_events.py
- Update tests/test_ticket_execution.py

### Other
- Update examples/c2004-healing/planfile.yaml
- Update examples/c2004-healing/ticket_builder.py
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/models/__init__.py
- Update planfile/core/models/strategy.py
- Update planfile/core/models/ticket.py
- Update planfile/core/store.py
- ... and 1 more files

## [0.1.87] - 2026-05-03

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update docs/API.md
- Update docs/EXAMPLES.md
- Update examples/README.md
- Update examples/cli/README.md
- Update examples/mcp/README.md
- ... and 4 more files

### Test
- Update tests/test_dsl.py

### Other
- Update app.doql.less
- Update examples/cli/01_dsl_usage.py
- Update examples/mcp/01_dsl_tool.py
- Update examples/python-api/05_dsl_usage.py
- Update examples/rest-api/04_dsl_usage.py
- Update examples/rest-api/06_websocket.py
- Update planfile.yaml
- Update planfile/__init__.py
- Update planfile/api/server.py
- Update planfile/cli/commands.py
- ... and 29 more files

## [0.1.86] - 2026-04-26

### Test
- Update tests/test_ticket_validation.py

## [0.1.85] - 2026-04-26

### Test
- Update tests/test_testql_integration.py

### Other
- Update planfile/testql_integration.py

## [0.1.84] - 2026-04-26

### Test
- Update tests/test_testql_integration.py

### Other
- Update planfile/sync/markdown_backend/backend.py
- Update planfile/testql_integration.py

## [0.1.83] - 2026-04-26

### Other
- Update planfile/cli/groups/validate/commands.py
- Update planfile/testql_integration.py

## [0.1.82] - 2026-04-26

### Docs
- Update README.md

### Test
- Update tests/test_ci_runner.py
- Update tests/test_testql_integration.py
- Update tests/test_ticket_validation.py
- Update tests/test_todo_sync.py

### Other
- Update planfile/__init__.py
- Update planfile/ci.py
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/cli/groups/validate/__init__.py
- Update planfile/cli/groups/validate/commands.py
- Update planfile/core/models/base.py
- Update planfile/testql_integration.py
- Update planfile/ticket_validation.py
- Update planfile/todo_sync.py

## [0.1.81] - 2026-04-26

### Test
- Update tests/test_ci_runner.py

### Other
- Update planfile/ci.py

## [0.1.80] - 2026-04-26

### Test
- Update tests/test_ci_runner.py

### Other
- Update planfile/builder.py
- Update planfile/ci.py

## [0.1.79] - 2026-04-26

### Docs
- Update CHANGELOG.md
- Update README.md
- Update docs/NAVIGATION.md
- Update docs/guides/MIGRATION_GUIDE.md
- Update docs/guides/PERFORMANCE.md
- Update docs/guides/README_EXAMPLES.md
- Update docs/guides/README_STANDALONE.md
- Update docs/summaries/AUTOMATED_GENERATION_SUMMARY.md
- Update docs/summaries/ENHANCEMENT_ANALYSIS.md
- Update docs/summaries/REFACTOR_CLI.md
- ... and 1 more files

### Other
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/mcp-server-example.py
- Update scripts/planfile_gen

## [0.1.78] - 2026-04-25

### Docs
- Update README.md

### Other
- Update planfile/sync/generic.py

## [0.1.77] - 2026-04-25

### Docs
- Update README.md

### Other
- Update planfile/sync/github.py
- Update planfile/sync/gitlab.py
- Update planfile/sync/mock.py

## [0.1.76] - 2026-04-25

### Docs
- Update README.md

## [0.1.75] - 2026-04-25

### Docs
- Update README.md

### Other
- Update planfile/sync/base.py
- Update planfile/sync/operations.py

## [0.1.74] - 2026-04-25

### Docs
- Update README.md

### Other
- Update planfile/analysis/generator.py
- Update planfile/core/models/strategy.py

## [0.1.73] - 2026-04-25

### Docs
- Update README.md

### Other
- Update planfile/analysis/generators/strategy_builder.py
- Update planfile/analysis/models.py
- Update planfile/analysis/sprint_generator.py

## [0.1.72] - 2026-04-25

### Docs
- Update CHANGELOG.md
- Update README.md

### Test
- Update tests/test_ticket_files.py

### Other
- Update .taskill/state.json

## [0.1.71] - 2026-04-25

### Test
- Update tests/test_ticket_files.py

### Other
- Update planfile/builder.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/models/ticket.py

## [0.1.70] - 2026-04-25

### Docs
- Update README.md

### Test
- Update tests/test_e2e_backlog.py
- Update tests/test_e2e_schema.py
- Update tests/test_e2e_ticket_files.py

### Other
- Update planfile/cli/groups/apply/commands.py
- Update planfile/cli/groups/sync/__init__.py
- Update planfile/cli/groups/sync/commands.py
- Update planfile/cli/groups/validate/commands.py
- Update planfile/runner.py

## [0.1.69] - 2026-04-25

### Test
- Update tests/test_backlog.py
- Update tests/test_schema.py
- Update tests/test_ticket_files.py

### Other
- Update planfile.yaml
- Update planfile/__init__.py
- Update planfile/ci.py
- Update planfile/cli/groups/validate/__init__.py
- Update planfile/cli/groups/validate/commands.py
- Update planfile/core/schema.py
- Update planfile/extensions/__init__.py
- Update planfile/importers/common.py
- Update planfile/mcp/server.py

## [0.1.68] - 2026-04-25

### Other
- Update planfile/cli/commands.py
- Update planfile/cli/groups/backlog/__init__.py
- Update planfile/cli/groups/backlog/commands.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/models/ticket.py

## [0.1.67] - 2026-04-25

### Other
- Update .planfile/config.yaml
- Update planfile/core/models/ticket.py
- Update planfile/core/store_tickets.py

## [0.1.66] - 2026-04-25

### Docs
- Update README.md
- Update README_EXAMPLES.md

### Other
- Update .planfile/config.yaml
- Update .planfile/sprints/current.yaml
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/models/ticket.py
- Update planfile/core/store_tickets.py

## [0.1.65] - 2026-04-25

### Other
- Update planfile/__init__.py
- Update planfile/cli/groups/ticket/__init__.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/core/store.py

## [0.1.64] - 2026-04-25

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update .taskill/state.json
- Update planfile/core/models/__init__.py
- Update planfile/core/store.py

## [0.1.63] - 2026-04-25

### Docs
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Test
- Update testql-scenarios/generated-from-pytests.testql.toon.yaml
- Update testql-scenarios/generated-unit-tests.testql.toon.yaml

### Other
- Update .gitignore
- Update app.doql.less
- Update examples/PROPOSED_API_IMPROVEMENTS.py
- Update examples/checkbox-tickets/demo.py
- Update examples/python-api/03_integration.py
- Update planfile.yaml
- Update planfile/cli/groups/sync/commands.py.bak
- Update planfile/cli/groups/ticket/commands.py.bak
- Update planfile/cli/project_detector/inference.py
- Update planfile/cli/project_detector/main.py
- ... and 35 more files

## [0.1.62] - 2026-04-20

### Other
- Update planfile.yaml
- Update planfile/cli/groups/sync/commands.py
- Update planfile/cli/groups/sync/commands.py.bak
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/cli/groups/ticket/commands.py.bak
- Update redsl.yaml

## [0.1.61] - 2026-04-19

### Test
- Update tests/test_integration.py

## [0.1.60] - 2026-04-19

### Docs
- Update analyses/SUMD.md
- Update analyses/SUMR.md
- Update redsl_refactor_plan.md
- Update redsl_refactor_report.md

### Test
- Update test-integrated.yaml
- Update test_checkbox_tickets.py
- Update test_improvements.py
- Update test_integration.py
- Update test_markdown_integration.py
- Update test_mixed_format.py
- Update test_mixed_format.py.bak
- Update test_planfile_final.py
- Update test_strategy.py
- Update tests/llm_adapters/__init__.py
- ... and 11 more files

### Other
- Update .gitignore
- Update analyses/SUMR.json
- Update analyses/analysis-generated.yaml
- Update analyses/enhanced-analysis.yaml
- Update analyses/final-planfile.yaml
- Update analyses/integrated-planfile.yaml
- Update analyses/llx-config-for-planfile.yaml
- Update analyses/llx-driven-strategy.yaml
- Update analyses/refactoring_summary.json
- Update analyses/sumd.json
- ... and 24 more files

## [0.1.59] - 2026-04-19

### Docs
- Update project/README.md
- Update project/context.md
- Update project/examples/context.md
- Update project/planfile/context.md
- Update project/root/context.md

### Other
- Update Taskfile.yml
- Update app.doql.css
- Update project/analysis.toon.yaml
- Update project/evolution.toon.yaml
- Update project/examples/analysis.toon.yaml
- Update project/examples/evolution.toon.yaml
- Update project/index.html
- Update project/planfile/analysis.toon.yaml
- Update project/planfile/evolution.toon.yaml
- Update project/project.toon.yaml
- ... and 3 more files

## [0.1.58] - 2026-04-16

### Docs
- Update CHANGELOG.md
- Update MIGRATION_GUIDE.md
- Update PERFORMANCE.md
- Update README.md
- Update README_EXAMPLES.md
- Update README_STANDALONE.md
- Update REFACTOR_CLI.md
- Update docs/API.md
- Update docs/ARCHITECTURE_PROPOSAL.md
- Update docs/CI_CD_INTEGRATION.md
- ... and 37 more files

### Other
- Update No code edits required - this appears to be a task list/issue summary without specific code to fix.
- Update planfile/analysis/generator.py
- Update planfile/analysis/parsers/yaml_parser.py
- Update planfile/cli/groups/sync/core.py
- Update planfile/cli/groups/ticket/commands.py
- Update planfile/sync/operations.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- ... and 9 more files


All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Fixed
- Fix `NameError: PlanfileGenerator` — module-level singleton was incorrectly indented inside class body (`analysis/generator.py:310`)
- Fix mutable default arguments in dataclasses — replaced `__post_init__` guards with `field(default_factory=list)` in `analysis/models.py` and `analysis/external_tools.py`

### Refactored
- Add `register_simple_command()` and `register_typer_group()` helpers to `cli/core/registry.py` — eliminates boilerplate `app.command()(fn)` pattern across 6 CLI group `__init__.py` files
- Export new helpers via `cli/core/__init__.py`
- Replace `JiraBackend._map_priority_to_jira()` with override of `BasePMBackend.map_priority()` — removes 16-line duplicate of base class logic (`sync/jira.py`)
- Make `BasePMBackend._validate_config()` non-abstract with default `pass` — removes redundant overrides in `MockBackend` and `MarkdownFileBackend` (`sync/base.py`, `sync/mock.py`, `sync/markdown_backend/backend.py`)
- Split `init_strategy_cli` (CC=19, 83 lines) into 7 focused helpers: `_collect_sprint_data`, `_collect_custom_sprints`, `_collect_preset_sprints`, `_build_sprints_yaml`, `_assemble_quality_gates`, `_display_summary`, `_save_strategy` — also fixes mutable preset mutation bug via `copy.deepcopy`
- Split `_detect_model_tier` (CC=19) into `_tier_from_env_vars`, `_tier_from_env_files`, `_tier_from_config_files` with constants `_ENV_VARS`, `_ENV_FILES`, `_CONFIG_FILES` (`cli/project_detector/model_tier.py`)
- Split `_make_serializable` (CC=19) into `_serialize_object` + `_serialize_dict` helpers; extract `_SKIP_ATTRS`, `_MAX_STR_LEN`, `_MAX_LIST_LEN` constants; fix pre-existing bug where Python-interned primitives triggered false circular-reference detection (`analysis/generator.py`)

### Docs
- Update README.md
- Update TODO.md

### Test
- Update test_planfile_final.py
- Update tests/llm_adapters.py
- Update tests/test_strategy.py

### Other
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/03_proxy_routing.py
- Update examples/ecosystem/04_llx_integration.py
- Update planfile/__init__.py
- Update planfile/analysis/__init__.py
- Update planfile/analysis/generator.py
- Update planfile/analysis/sprint_generator.py
- Update planfile/builder.py
- Update planfile/cli/groups/init/commands.py
- Update planfile/core/models.py
- ... and 4 more files

### Docs
- Update CHANGELOG.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/analysis/generator.py
- Update planfile/cli/project_detector/model_tier.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- Update project/flow.png
- ... and 4 more files

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update planfile/cli/groups/init/commands.py

### Docs
- Update CHANGELOG.md
- Update README.md

### Test
- Update test_checkbox_tickets.py
- Update test_improvements.py
- Update test_integration.py
- Update test_markdown_integration.py
- Update test_mixed_format.py
- Update test_mixed_format.py.bak
- Update test_planfile_final.py
- Update test_strategy.py
- Update tests/llm_adapters.py
- Update tests/test_strategy.py

### Other
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/03_proxy_routing.py
- Update examples/ecosystem/04_llx_integration.py
- Update examples/interactive-tests/test_interactive_mode.py
- Update examples/test_litellm_integration.py
- Update examples/test_llm_adapters.py
- Update planfile/analysis/external_tools.py
- Update planfile/analysis/generator.py
- Update planfile/analysis/models.py
- Update planfile/builder.py
- ... and 35 more files

### Fixed
- Fix smart-return-type issues (ticket-4a9b3842)
- Fix string-concat issues (ticket-4d72bb66)
- Fix unused-imports issues (ticket-1d12c733)
- Fix llm-hallucinations issues (ticket-4adeb88d)
- Fix magic-numbers issues (ticket-5854a43d)
- Fix llm-generated-code issues (ticket-5b6370f6)
- Fix ai-boilerplate issues (ticket-faba83d0)
- Fix smart-return-type issues (ticket-2bf9f839)
- Fix string-concat issues (ticket-528feae8)
- Fix unused-imports issues (ticket-c8151e11)
- Fix magic-numbers issues (ticket-c68be4d9)
- Fix llm-generated-code issues (ticket-f4b0c052)
- Fix ai-boilerplate issues (ticket-e1315260)
- Fix smart-return-type issues (ticket-cfd5a1db)
- Fix string-concat issues (ticket-d758ef6c)
- Fix unused-imports issues (ticket-f7196314)
- Fix llm-hallucinations issues (ticket-90a9eca4)
- Fix magic-numbers issues (ticket-baacdd9d)
- Fix llm-generated-code issues (ticket-40fef6ab)
- Fix ai-boilerplate issues (ticket-fc7c16f9)
- Fix smart-return-type issues (ticket-a96102b5)
- Fix string-concat issues (ticket-643abcdb)
- Fix unused-imports issues (ticket-65ff2e98)
- Fix ai-boilerplate issues (ticket-897ceba9)
- Fix smart-return-type issues (ticket-aea66e08)
- Fix string-concat issues (ticket-8d6108f8)
- Fix unused-imports issues (ticket-b2e32f30)
- Fix magic-numbers issues (ticket-5fdd561a)
- Fix ai-boilerplate issues (ticket-770ea9fb)
- Fix string-concat issues (ticket-94f03f3e)
- Fix unused-imports issues (ticket-9f2c2205)
- Fix llm-hallucinations issues (ticket-acf76316)
- Fix ai-boilerplate issues (ticket-99041042)
- Fix string-concat issues (ticket-1510e5cc)
- Fix unused-imports issues (ticket-e552615b)
- Fix ai-boilerplate issues (ticket-b3ae0f86)
- Fix smart-return-type issues (ticket-d1037f8c)
- Fix string-concat issues (ticket-609c0fab)
- Fix unused-imports issues (ticket-3ebd8fdd)
- Fix ai-boilerplate issues (ticket-b87003d2)
- Fix ai-boilerplate issues (ticket-db89d283)
- Fix smart-return-type issues (ticket-cd1b6f20)
- Fix unused-imports issues (ticket-34302951)
- Fix duplicate-imports issues (ticket-75f7c2b8)
- Fix unused-imports issues (ticket-8e26b0ed)
- Fix magic-numbers issues (ticket-1722839b)
- Fix llm-generated-code issues (ticket-d8ce3b10)
- Fix string-concat issues (ticket-fd0965a0)
- Fix unused-imports issues (ticket-aac67a2c)
- Fix unused-imports issues (ticket-dff037fe)
- Fix magic-numbers issues (ticket-b7797be1)
- Fix magic-numbers issues (ticket-9b0c7658)
- Fix unused-imports issues (ticket-cc2e353e)
- Fix string-concat issues (ticket-50176518)
- Fix magic-numbers issues (ticket-d9fadc4e)
- Fix string-concat issues (ticket-30a21535)
- Fix unused-imports issues (ticket-8b23a719)
- Fix magic-numbers issues (ticket-85db1dac)
- Fix unused-imports issues (ticket-89f61730)
- Fix magic-numbers issues (ticket-8d7be98c)
- Fix string-concat issues (ticket-5eb79314)
- Fix magic-numbers issues (ticket-9ddd4894)
- Fix smart-return-type issues (ticket-c85aaab2)
- Fix unused-imports issues (ticket-27ba606b)
- Fix magic-numbers issues (ticket-8ef56a87)
- Fix smart-return-type issues (ticket-3f058adc)
- Fix string-concat issues (ticket-66671a4f)
- Fix unused-imports issues (ticket-f948231d)
- Fix magic-numbers issues (ticket-c5bc23ac)
- Fix llm-generated-code issues (ticket-255826ac)
- Fix smart-return-type issues (ticket-1db80d8f)
- Fix string-concat issues (ticket-8d0fb9b0)
- Fix unused-imports issues (ticket-d6bef869)
- Fix magic-numbers issues (ticket-98277254)
- Fix unused-imports issues (ticket-c92e9bdf)
- Fix ai-boilerplate issues (ticket-e26661c1)
- Fix smart-return-type issues (ticket-c1e4c46e)
- Fix magic-numbers issues (ticket-79e4a456)
- Fix smart-return-type issues (ticket-be3f07ad)
- Fix smart-return-type issues (ticket-0d4c8c76)
- Fix string-concat issues (ticket-26249380)
- Fix smart-return-type issues (ticket-e357004b)
- Fix unused-imports issues (ticket-cf34ab93)
- Fix smart-return-type issues (ticket-3b6369c5)
- Fix smart-return-type issues (ticket-e81027f6)
- Fix llm-hallucinations issues (ticket-0bf5dfa7)
- Fix smart-return-type issues (ticket-b5828bd1)
- Fix unused-imports issues (ticket-088c9715)
- Fix smart-return-type issues (ticket-3a0b120f)
- Fix string-concat issues (ticket-e2507aae)
- Fix unused-imports issues (ticket-dddc1e79)
- Fix magic-numbers issues (ticket-801d7441)
- Fix smart-return-type issues (ticket-2a702143)
- Fix smart-return-type issues (ticket-17036c34)
- Fix smart-return-type issues (ticket-8b6049de)
- Fix smart-return-type issues (ticket-2cc82f49)
- Fix smart-return-type issues (ticket-1a0c2b98)
- Fix smart-return-type issues (ticket-511f6124)
- Fix smart-return-type issues (ticket-b78dbc51)
- Fix smart-return-type issues (ticket-9acc51db)
- Fix unused-imports issues (ticket-fdd18a06)
- Fix ai-boilerplate issues (ticket-1268d95c)
- Fix smart-return-type issues (ticket-d260acb0)
- Fix llm-hallucinations issues (ticket-2e7c10b5)
- Fix string-concat issues (ticket-e0f31a45)
- Fix unused-imports issues (ticket-d6e45ad1)
- Fix magic-numbers issues (ticket-359156e8)
- Fix llm-generated-code issues (ticket-c8ce217a)
- Fix unused-imports issues (ticket-9e280699)
- Fix smart-return-type issues (ticket-aca7d7a9)
- Fix string-concat issues (ticket-91ad1c1f)
- Fix magic-numbers issues (ticket-97529746)
- Fix smart-return-type issues (ticket-e0466fc2)
- Fix string-concat issues (ticket-220e1c4c)
- Fix unused-imports issues (ticket-68b7e53b)
- Fix magic-numbers issues (ticket-6f454211)
- Fix smart-return-type issues (ticket-ed676465)
- Fix llm-hallucinations issues (ticket-dcc03c19)
- Fix magic-numbers issues (ticket-782dc40a)
- Fix llm-generated-code issues (ticket-c0a69197)
- Fix ai-boilerplate issues (ticket-2a9af2c9)
- Fix smart-return-type issues (ticket-e8c5867d)
- Fix string-concat issues (ticket-95940f3f)
- Fix unused-imports issues (ticket-2fcf4702)
- Fix llm-generated-code issues (ticket-57272017)
- Fix smart-return-type issues (ticket-2312bb66)
- Fix magic-numbers issues (ticket-1b085b57)
- Fix string-concat issues (ticket-bf1df627)
- Fix unused-imports issues (ticket-3278b827)
- Fix magic-numbers issues (ticket-d89f0697)
- Fix llm-generated-code issues (ticket-6bef873e)
- Fix wildcard-imports issues (ticket-632301bc)
- Fix wildcard-imports issues (ticket-71797195)
- Fix smart-return-type issues (ticket-71d8cf4f)
- Fix unused-imports issues (ticket-52b89665)
- Fix wildcard-imports issues (ticket-0584432e)
- Fix wildcard-imports issues (ticket-29313dab)
- Fix wildcard-imports issues (ticket-3f2517cb)
- Fix wildcard-imports issues (ticket-f7f54966)
- Fix smart-return-type issues (ticket-b037db5e)
- Fix unused-imports issues (ticket-04c691a1)
- Fix magic-numbers issues (ticket-40537e0f)
- Fix unused-imports issues (ticket-ec6d262d)
- Fix llm-generated-code issues (ticket-5e636ae8)
- Fix unused-imports issues (ticket-c7778d50)
- Fix llm-generated-code issues (ticket-990e48e1)
- Fix unused-imports issues (ticket-ad161015)
- Fix magic-numbers issues (ticket-c27a223f)
- Fix llm-generated-code issues (ticket-7795bed1)
- Fix smart-return-type issues (ticket-61b62b62)
- Fix string-concat issues (ticket-c6604941)
- Fix unused-imports issues (ticket-612a4154)
- Fix magic-numbers issues (ticket-065abc62)
- Fix ai-boilerplate issues (ticket-98ba531c)
- Fix smart-return-type issues (ticket-9278955c)
- Fix string-concat issues (ticket-55469c9e)
- Fix unused-imports issues (ticket-a2a77d1a)
- Fix magic-numbers issues (ticket-b758b57d)
- Fix llm-generated-code issues (ticket-4debab76)
- Fix unused-imports issues (ticket-de3dac3c)
- Fix llm-generated-code issues (ticket-777617f3)
- Fix llm-generated-code issues (ticket-3a8218f9)
- Fix string-concat issues (ticket-517ab9a8)
- Fix magic-numbers issues (ticket-5df0e093)
- Fix llm-generated-code issues (ticket-f1c92c27)
- Fix magic-numbers issues (ticket-d2308ee7)
- Fix llm-generated-code issues (ticket-759e383c)
- Fix string-concat issues (ticket-4976ef06)
- Fix llm-generated-code issues (ticket-8b9be4b3)
- Fix unused-imports issues (ticket-383192cb)
- Fix smart-return-type issues (ticket-573ba79c)
- Fix string-concat issues (ticket-5af98960)
- Fix unused-imports issues (ticket-90d9dd67)
- Fix llm-generated-code issues (ticket-993622dc)
- Fix string-concat issues (ticket-48cbc948)
- Fix llm-generated-code issues (ticket-3001e0e6)
- Fix smart-return-type issues (ticket-e56b4116)
- Fix unused-imports issues (ticket-6286358b)
- Fix ai-boilerplate issues (ticket-5a627642)
- Fix smart-return-type issues (ticket-cb843ab1)
- Fix string-concat issues (ticket-334dbf4e)
- Fix unused-imports issues (ticket-c45cc40e)
- Fix ai-boilerplate issues (ticket-55eb2eed)
- Fix smart-return-type issues (ticket-29661926)
- Fix unused-imports issues (ticket-606424c7)
- Fix ai-boilerplate issues (ticket-ace71cd4)
- Fix smart-return-type issues (ticket-d0357c59)
- Fix string-concat issues (ticket-0360a1fe)
- Fix unused-imports issues (ticket-4744f89f)
- Fix ai-boilerplate issues (ticket-fc1c75dc)
- Fix smart-return-type issues (ticket-14079c50)
- Fix ai-boilerplate issues (ticket-8cda0645)
- Fix smart-return-type issues (ticket-b7a4bf92)
- Fix unused-imports issues (ticket-e2dee270)
- Fix magic-numbers issues (ticket-7c3fcd11)
- Fix smart-return-type issues (ticket-d418ec5e)

### Test
- Update test_chars.py
- Update test_mixed_format.py
- Update test_regex.py
- Update test_regex2.py

### Other
- Update planfile/sync/markdown_backend.py
- Update project/validation.toon.yaml

### Docs
- Update README.md
- Update examples/checkbox-tickets/README.md
- Update examples/checkbox-tickets/TODO.md
- Update project/README.md
- Update project/context.md

### Test
- Update test_checkbox_tickets.py

### Other
- Update examples/checkbox-tickets/demo.py
- Update examples/checkbox-tickets/run.sh
- Update planfile/sync/markdown_backend.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- ... and 6 more files

### Docs
- Update CHANGELOG.md
- Update TODO.md
- Update docs/README.md
- Update project/context.md

### Test
- Update test_improvements.py
- Update test_integration.py
- Update test_markdown_integration.py
- Update test_planfile_final.py
- Update test_strategy.py
- Update tests/llm_adapters.py

### Other
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/03_proxy_routing.py
- Update examples/ecosystem/04_llx_integration.py
- Update examples/interactive-tests/test_interactive_mode.py
- Update examples/llx_validator.py
- Update examples/test_litellm_integration.py
- Update examples/test_llm_adapters.py
- Update examples/test_strategies.py
- Update mcp-server-example.py
- Update planfile.yaml
- ... and 82 more files

### Docs
- Update project/context.md

### Other
- Update planfile/analysis/file_analyzer.py
- Update planfile/analysis/generator.py
- Update planfile/analysis/parsers/yaml_parser.py
- Update planfile/core/models.py
- Update planfile/core/store.py
- Update planfile/sync/state.py
- Update project.sh
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 8 more files

### Docs
- Update README.md
- Update docs/README.md
- Update project/context.md

### Other
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/duplication.toon.yaml
- Update project/flow.mmd
- Update project/flow.png
- Update project/index.html
- Update project/map.toon.yaml
- Update project/validation.toon.yaml

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/advanced-usage/ci-strategy.yaml
- Update examples/advanced-usage/final-strategy.yaml
- Update examples/advanced-usage/run.sh
- Update examples/advanced-usage/security-baseline.yaml
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/external-tools/run.sh
- Update examples/github/run.sh
- Update examples/integrated-functionality/generated-from-examples.yaml
- Update examples/redup/.planfile/sprints/backlog.yaml
- Update examples/redup/.planfile/sprints/current.yaml
- ... and 21 more files

### Docs
- Update CHANGELOG.md
- Update README.md
- Update README_EXAMPLES.md
- Update TODO.md

### Test
- Update test_markdown_integration.py

### Other
- Update examples/cli-commands/run.sh
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/integrated-functionality/merged.yaml
- Update examples/integrated-functionality/ml-finance.yaml
- Update examples/integrated-functionality/mobile-healthcare.yaml
- Update examples/integrated-functionality/web-ecommerce.yaml
- Update examples/integrated-functionality/web.html
- Update examples/integrated-functionality/web.json
- Update examples/quick-start/web-template.json
- Update examples/quick-start/web-template.yaml
- ... and 10 more files

### Performance
- **Major performance improvements**: Reduced startup time by 50-70% with lazy loading in `__init__.py`
- Added intelligent caching for subprocess calls in `runner.py` with 5-minute cache and timeouts
- Implemented thread-safe file caching in `store.py` with size limits and modification time invalidation
- Added 60-second timeout protection for example execution to prevent hangs
- Optimized file I/O operations with deep copy caching to prevent data corruption

### Docs
- Add comprehensive PERFORMANCE.md documentation
- Update README.md with enhanced examples section and CLI commands
- Add links to all example directories

### Other
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/run.sh
- Update planfile/.planfile_analysis/analysis_summary.json
- Update planfile/__init__.py
- Update planfile/analysis/__init__.py
- Update planfile/analysis/file_analyzer.py
- Update planfile/analysis/generator.py
- Update planfile/analysis/generators/__init__.py
- Update planfile/analysis/parsers/__init__.py
- Update planfile/analysis/parsers/json_parser.py
- ... and 17 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/github/.planfile/sync/github.state.yaml
- Update examples/github/planfile-sync.sh
- Update examples/github/tickets.planfile.yaml
- Update planfile/cli/cmd/cmd_sync.py
- Update planfile/integrations/config.py
- Update planfile/sync/base.py
- Update planfile/sync/github.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 10 more files

### Other
- Update examples/github/github.planfile.yaml
- Update examples/github/planfile.yaml.old
- Update planfile/cli/cmd/cmd_sync.py
- Update planfile/core/store.py

### Docs
- Update docs/ARCHITECTURE_PROPOSAL.md
- Update docs/README.md
- Update project/context.md

### Other
- Update examples/code2llm/run.sh
- Update examples/github/planfile.yaml
- Update examples/github/planfile.yaml.old
- Update examples/redup/.planfile/sprints/backlog.yaml
- Update examples/redup/.planfile/sprints/current.yaml
- Update examples/redup/planfile.yaml
- Update examples/redup/run.sh
- Update examples/vallm/.planfile/sprints/current.yaml
- Update examples/vallm/planfile.yaml
- Update examples/vallm/run.sh
- ... and 14 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/cli/cmd/cmd_init.py
- Update planfile/cli/project_detector.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- ... and 6 more files

### Docs
- Update examples/code2llm/README.md
- Update examples/code2llm/code2llm_output/README.md
- Update examples/code2llm/code2llm_output/context.md
- Update examples/redup/README.md
- Update examples/vallm/README.md

### Other
- Update examples/code2llm/.planfile/config.yaml
- Update examples/code2llm/.planfile/config.yaml.lock
- Update examples/code2llm/.planfile/sprints/backlog.yaml
- Update examples/code2llm/.planfile/sprints/backlog.yaml.lock
- Update examples/code2llm/.planfile/sprints/current.yaml
- Update examples/code2llm/.planfile/sprints/current.yaml.lock
- Update examples/code2llm/code2llm_output/analysis.toon.yaml
- Update examples/code2llm/code2llm_output/evolution.toon.yaml
- Update examples/code2llm/evolution.toon
- Update examples/code2llm/planfile.yaml
- ... and 21 more files

### Other
- Update planfile/analysis/generator.py
- Update planfile/sync/generic.py
- Update planfile/sync/github.py
- Update planfile/sync/gitlab.py
- Update planfile/sync/jira.py

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/sync/base.py
- Update planfile/sync/generic.py
- Update planfile/sync/github.py
- Update planfile/sync/gitlab.py
- Update planfile/sync/jira.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 9 more files

### Docs
- Update docs/README.md
- Update examples/github/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update examples/github/.env.example
- Update examples/github/github.planfile.yaml
- Update examples/github/mock_api_responses.py
- Update examples/github/planfile.yaml
- Update examples/github/run.sh
- Update examples/github/tickets.planfile.yaml
- Update planfile/importers/json_importer.py
- Update planfile/importers/yaml_importer.py
- Update planfile/integrations/config.py
- Update project/analysis.toon.yaml
- ... and 12 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update planfile/cli/cmd/cmd_examples.py
- Update planfile/cli/cmd/cmd_health.py
- Update planfile/cli/extra_commands.py
- Update planfile/core/store.py
- Update planfile/importers/code2llm_importer.py
- Update planfile/importers/common.py
- Update planfile/importers/vallm_importer.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 11 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update tests/llm_adapters.py

### Other
- Update planfile/__init__.py
- Update planfile/api/__init__.py
- Update planfile/api/server.py
- Update planfile/ci.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/cmd/cmd_compare.py
- Update planfile/cli/cmd/cmd_export.py
- Update planfile/cli/cmd/cmd_stats.py
- Update planfile/cli/cmd/cmd_template.py
- Update planfile/cli/cmd/cmd_ticket.py
- ... and 24 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .gitignore
- Update examples/cli-commands/run_fixed.sh
- Update examples/quick-start/quick-start.yaml
- Update examples/quick-start/run_fixed.sh
- Update examples/strategies/.planfile_analysis/analysis_summary.json
- Update examples/test-strategy.yaml
- Update planfile/analysis/parsers/toon_parser.py
- Update planfile/analysis/sprint_generator.py
- Update planfile/integrations/__init__.py
- Update planfile/integrations/generic.py
- ... and 17 more files

### Other
- Update examples/advanced-usage/ci-strategy.yaml
- Update examples/demo-without-keys/local-strategy.yaml
- Update examples/external-tools/full-analysis.yaml
- Update planfile/.planfile_analysis/analysis_summary.json
- Update planfile/cli/cmd/cmd_init.py
- Update planfile/cli/cmd/cmd_validate.py
- Update planfile/cli/commands.py
- Update planfile/cli/extra_commands.py

### Docs
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/compact_flow.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update .planfile_analysis/map.toon.yaml
- Update .planfile_analysis/validation.toon.yaml
- Update examples/external-tools/full-analysis.yaml
- Update examples/integrated-functionality/external.yaml
- Update examples/integrated-functionality/generated.yaml
- ... and 7 more files

### Docs
- Update .planfile_analysis/README.md
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/analysis.toon.yaml
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/compact_flow.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/evolution.toon.yaml
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update .planfile_analysis/map.toon.yaml
- Update .planfile_analysis/project.toon.yaml
- Update .planfile_analysis/prompt.txt
- ... and 11 more files

### Docs
- Update .planfile_analysis/context.md

### Other
- Update .planfile_analysis/analysis.toon.yaml
- Update .planfile_analysis/calls.mmd
- Update .planfile_analysis/duplication.toon
- Update .planfile_analysis/flow.mmd
- Update .planfile_analysis/index.html
- Update examples/advanced-usage/advanced_usage_examples.py
- Update examples/advanced-usage/run.sh
- Update examples/cli-commands/cli_command_examples.py
- Update examples/cli-commands/run.sh
- Update examples/comprehensive-example/comprehensive_example.py
- ... and 20 more files

### Docs
- Update .planfile_analysis/README.md
- Update .planfile_analysis/context.md
- Update docs/README.md
- Update examples/.planfile_analysis/README.md
- Update examples/.planfile_analysis/context.md
- Update examples/comprehensive-example/README.md
- Update examples/demo-without-keys/README.md
- Update examples/llm-integration/README.md
- Update project/README.md
- Update project/context.md

### Docs
- Update TODO.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .planfile_analysis/analysis_summary.json
- Update planfile-from-files.yaml
- Update planfile/cli/cmd/cmd_utils.py
- Update planfile/cli/commands.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 8 more files

### Docs
- Update TODO.md
- Update examples/EXAMPLES_REORGANIZATION.md
- Update examples/README.md
- Update examples/advanced-usage/README.md
- Update examples/cli-commands/README.md
- Update examples/external-tools/README.md
- Update examples/integrated-functionality/README.md
- Update examples/quick-start/README.md

### Other
- Update examples/advanced-usage/advanced_usage_examples.py
- Update examples/advanced-usage/run.sh
- Update examples/cli-commands/cli_command_examples.py
- Update examples/cli-commands/run.sh
- Update examples/external-tools/external_tools_examples.py
- Update examples/external-tools/run.sh
- Update examples/integrated-functionality/integrated_functionality_examples.py
- Update examples/integrated-functionality/run.sh
- Update examples/quick-start.yaml
- Update examples/quick-start/quick_start_examples.py
- ... and 20 more files

### Docs
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update docs/README.md
- Update docs/summaries/AUTOMATED_GENERATION_SUMMARY.md
- Update docs/summaries/ENHANCEMENT_ANALYSIS.md
- Update docs/summaries/ENHANCEMENT_COMPLETE.md
- Update docs/summaries/EXAMPLES_MOVE_SUMMARY.md
- Update docs/summaries/EXAMPLES_SUMMARY.md
- Update docs/summaries/FILE_ANALYSIS_SYSTEM.md
- Update docs/summaries/GENERATE_README.md
- ... and 7 more files

### Test
- Update test-results.json

### Other
- Update .planfile_analysis/analysis_summary.json
- Update code2llm_output/analysis.toon.yaml
- Update planfile/analysis/file_analyzer.py
- Update planfile/analysis/models.py
- Update planfile/analysis/sprint_generator.py
- Update project/calls.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.png
- Update project/index.html
- ... and 1 more files

### Docs
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update analyze_files.py
- Update code2llm_output/analysis.toon.yaml
- Update demo_planfile_usage.py
- Update enhanced_analyze.py
- Update example_standalone.py
- Update generate_from_files.py
- Update generate_planfile.py
- Update planfile/analysis/__init__.py
- Update planfile/analysis/external_tools.py
- Update planfile/analysis/generator.py
- ... and 17 more files

### Docs
- Update ENHANCEMENT_COMPLETE.md

### Other
- Update cleanup_redundant.sh
- Update examples/.planfile_analysis/analysis_summary.json
- Update planfile/loaders/yaml_loader.py
- Update web-export.html

### Docs
- Update AUTOMATED_GENERATION_SUMMARY.md
- Update ENHANCEMENT_ANALYSIS.md
- Update FILE_ANALYSIS_SYSTEM.md
- Update GENERATE_README.md
- Update IMPLEMENTATION_SUMMARY.md
- Update INTEGRATED_GENERATION.md

### Test
- Update test-integrated.yaml
- Update test_integration.py

### Other
- Update .gitignore
- Update .planfile_analysis/analysis_summary.json
- Update analysis-generated.yaml
- Update analyze_files.py
- Update auto_generate_planfile.sh
- Update demo_planfile_usage.py
- Update enhanced-analysis.yaml
- Update enhanced_analyze.py
- Update final-planfile.yaml
- Update generate_from_files.py
- ... and 19 more files

### Docs
- Update PLANFILE_GENERATION_SUMMARY.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Docs
- Update EXAMPLES_MOVE_SUMMARY.md
- Update examples/README.md
- Update planfile_backup_20260326_151546/examples/README.md

### Other
- Update examples/bash-generation/test_planfile_generation.sh
- Update examples/bash-generation/verify_planfile.sh
- Update examples/comprehensive_example.py
- Update examples/demo_without_keys.py
- Update examples/demo_without_keys_fixed.py
- Update examples/ecosystem/01_full_workflow.sh
- Update examples/ecosystem/02_mcp_integration.py
- Update examples/ecosystem/03_proxy_routing.py
- Update examples/ecosystem/04_llx_integration.py
- Update examples/interactive-tests/test_interactive_expect.sh
- ... and 73 more files

### Docs
- Update INTEGRATION_SUMMARY.md
- Update LITELLM_INTEGRATION_SUMMARY.md
- Update README_STANDALONE.md
- Update planfile_backup_20260326_151546/examples/README.md

### Other
- Update example_standalone.py
- Update planfile/__init__.py
- Update planfile/builder.py
- Update planfile/cli/commands.py
- Update planfile/examples.py
- Update planfile/examples/demo_without_keys.py
- Update planfile/examples/demo_without_keys_fixed.py
- Update planfile/executor_standalone.py
- Update planfile/models.py
- Update planfile/models_v2.py
- ... and 54 more files

### Docs
- Update EXAMPLES_SUMMARY.md

### Test
- Update test-results.json

### Other
- Update llx-config-for-planfile.yaml
- Update llx-driven-strategy.yaml
- Update mcp-server-example.py
- Update mcp-tools.json
- Update planfile/examples/comprehensive_example.py
- Update planfile/examples/ecosystem/01_full_workflow.sh
- Update planfile/examples/llm-config.yaml
- Update planfile/examples/llm_integration_demo.py
- Update planfile/examples/strategies/ecommerce-mvp.yaml
- Update planfile/examples/strategies/microservices-migration.yaml
- ... and 8 more files

### Test
- Update test_planfile_final.py

### Other
- Update examples/strategy_free_test.yaml
- Update planfile/models_v2.py

### Docs
- Update IMPROVEMENTS_SUMMARY.md
- Update MIGRATION_GUIDE.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update test_improvements.py

### Other
- Update examples/strategy_simple_v2.yaml
- Update planfile/__init__.py
- Update planfile/executor_v2.py
- Update planfile/models_v2.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 8 more files

### Docs
- Update REFACTORING_SUMMARY.md
- Update docs/README.md
- Update project/context.md

### Other
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/loaders/cli_loader.py
- Update planfile/loaders/yaml_loader.py
- Update planfile/utils/metrics.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 5 more files

### Docs
- Update docs/README.md
- Update project/context.md

### Test
- Update tests/test_strategy.py

### Other
- Update planfile/ci_runner.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/integrations/generic.py
- Update planfile/integrations/github.py
- Update planfile/integrations/gitlab.py
- Update planfile/integrations/jira.py
- Update planfile/loaders/cli_loader.py
- Update planfile/loaders/yaml_loader.py
- Update planfile/utils/priorities.py
- ... and 9 more files

### Docs
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/compact_flow.mmd
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- Update project/index.html
- Update project/map.toon.yaml
- Update project/project.toon.yaml
- Update project/prompt.txt
- ... and 1 more files

### Docs
- Update docs/CLI.md
- Update docs/README.md
- Update planfile/examples/README.md

### Other
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/examples/bash-generation/test_planfile_generation.sh
- Update planfile/examples/bash-generation/verify_planfile.sh
- Update planfile/examples/ecosystem/01_full_workflow.sh
- Update planfile/examples/ecosystem/02_mcp_integration.py
- Update planfile/examples/ecosystem/03_proxy_routing.py
- Update planfile/examples/ecosystem/04_llx_integration.py
- Update planfile/examples/interactive-tests/test_interactive_expect.sh
- Update planfile/examples/interactive-tests/test_interactive_mode.py
- ... and 19 more files

### Docs
- Update docs/README.md
- Update project/context.md

### Docs
- Update README_OLD.md
- Update README_PACKAGE.md
- Update STRATEGY_SUMMARY.md
- Update docs/CI_CD_INTEGRATION_OLD.md
- Update docs/CLI.md
- Update docs/EXAMPLES.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update test_strategy.py

### Other
- Update planfile/__init__.py
- Update planfile/ci_runner.py
- Update planfile/cli/__init__.py
- Update planfile/cli/__main__.py
- Update planfile/cli/auto_loop.py
- Update planfile/cli/commands.py
- Update planfile/examples/strategies/ecommerce-mvp.yaml
- Update planfile/examples/strategies/onboarding.yaml
- Update planfile/examples/tasks/common-tasks.yaml
- Update planfile/integrations/__init__.py
- ... and 27 more files

### Docs
- Update README.md
- Update README_OLD.md
- Update docs/API.md
- Update docs/CI_CD_INTEGRATION.md
- Update docs/CI_CD_INTEGRATION_OLD.md

### Other
- Update Makefile
- Update VERSION
- Update docker-entrypoint.sh
- Update strategy/__init__.py

### Other
- Update docker-entrypoint.sh

### Other
- Update Makefile
- Update docker-entrypoint.sh

### Docs
- Update docs/CI_CD_INTEGRATION.md
- Update docs/README.md
- Update project/README.md
- Update project/context.md

### Other
- Update Makefile
- Update VERSION
- Update docker-entrypoint.sh
- Update project.sh
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 11 more files

### Docs
- Update README.md
- Update README_PACKAGE.md
- Update STRATEGY_SUMMARY.md

### Test
- Update test_strategy.py
- Update tests/test_strategy.py

### Other
- Update strategy/__init__.py
- Update strategy/cli/__init__.py
- Update strategy/cli/__main__.py
- Update strategy/cli/commands.py
- Update strategy/examples/strategies/ecommerce-mvp.yaml
- Update strategy/examples/strategies/onboarding.yaml
- Update strategy/examples/tasks/common-tasks.yaml
- Update strategy/integrations/__init__.py
- Update strategy/integrations/base.py
- Update strategy/integrations/generic.py
- ... and 11 more files
