---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "executor-metrics",
  "kind": "information",
  "version": 1,
  "title": "Optional executor metrics and incomplete file reads",
  "status": "implemented",
  "owner": "semcod/planfile",
  "created": "2026-09-09",
  "updated": "2026-09-09",
  "review_after": "2026-10-09",
  "source_revision": "59dcc7a65f04de5cb31f4caa99df157697875058",
  "affected_repositories": ["semcod/planfile"],
  "evidence": [
    "https://github.com/semcod/planfile/blob/59dcc7a65f04de5cb31f4caa99df157697875058/planfile/executor_standalone.py",
    "https://github.com/subactor/doctor-agent/issues/377",
    "https://github.com/subactor/doctor-agent/issues/378",
    "repo://semcod/planfile/tests/test_executor_metrics.py"
  ]
}
---

# Optional executor metrics and incomplete file reads

<!-- docs:section purpose -->
## Purpose

Make a missing portion of optional project context visible to operators and LLM
consumers. At the baseline source revision above, the standalone executor caught
all exceptions during project metrics collection without recording a diagnostic.
Doctor detected both the per-file catch and the outer fallback.

<!-- docs:section scope -->
## Scope

This document describes `StrategyExecutor._get_project_metrics` and the prompt
it supplies to the standalone executor. The source revision identifies the
investigated baseline; the implementation and regression tests are versioned
with this document. Publication and runtime deployment require separate receipts.

<!-- docs:section evidence -->
## Evidence

`tests/test_executor_metrics.py` reproduces undecodable Python input, denied file
reads, enumeration failure and an unexpected programming error. Before the fix,
five regression cases failed because the collector omitted coverage state,
emitted no diagnostic, or swallowed a programming error. The suite also checks
that partial file-read coverage reaches the LLM prompt.

The local full test run completed with 475 passed and 6 skipped tests. Six tests
cover this change. Required hosted checks and independent publication are recorded
on the delivery PR, separately from this local result.

<!-- docs:section content -->
## Behavior

Expected file read errors (`OSError`, `UnicodeDecodeError`) keep the best-effort
metrics path available. The returned dictionary retains the existing metric
fields and adds `files_failed` and `complete`. The prompt includes both fields.

The module logger emits stable warning codes:

| Code | Meaning |
| --- | --- |
| `PLANFILE_METRICS_FILE_READ_FAILED` | A discovered Python file could not be read; its content is omitted. |
| `PLANFILE_METRICS_UNAVAILABLE` | An outer filesystem operation failed; optional metrics return `None`. |

Warnings include the exception class only. They omit exception messages, file
paths and source contents. Unexpected programming errors propagate from the
collector to the existing caller error boundary. Module-level logger initialization
also makes that boundary usable when the executor is imported as a library.

<!-- docs:section limitations -->
## Limitations

`complete` means no observed file-read failure among files processed by this
collector. It does not certify whole-repository coverage, filesystem snapshot
consistency, absence of symlink traversal or accurate cyclomatic complexity.
The existing keyword-count estimate and denominator remain unchanged. An outer
filesystem failure produces a warning and no metrics section in the prompt.

These changes do not authorize repairs or replace the scanner and Planfile/GitHub
projection described in the [published Doctor integration report](https://github.com/subactor/docs/blob/9a8dc3769e2dfeddbb65c4648c42496406d98679/architecture/analysis/organism-guard-integration.md).

<!-- docs:section next_actions -->
## Next actions

Use these codes when diagnosing incomplete executor context. Resolve any follow-up
about complexity accuracy or filesystem enumeration as a separately scoped change.
