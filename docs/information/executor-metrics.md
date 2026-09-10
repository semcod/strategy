---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "executor-metrics",
  "kind": "information",
  "version": 2,
  "title": "Optional executor metrics and incomplete file reads",
  "status": "implemented",
  "owner": "semcod/planfile",
  "created": "2026-09-09",
  "updated": "2026-09-10",
  "review_after": "2026-10-09",
  "source_revision": "51b0c94f01d78a0d82ff92b998114e5ae6b9fffa",
  "affected_repositories": ["semcod/planfile"],
  "evidence": [
    "https://github.com/semcod/planfile/blob/59dcc7a65f04de5cb31f4caa99df157697875058/planfile/executor_standalone.py",
    "https://github.com/subactor/doctor-agent/issues/377",
    "https://github.com/subactor/doctor-agent/issues/378",
    "repo://semcod/planfile/tests/test_executor_metrics.py",
    "https://github.com/semcod/planfile/pull/62",
    "receipt:planfile:PLF-13798:metrics-deployment"
  ]
}
---

# Optional executor metrics and incomplete file reads

<!-- docs:section purpose -->
## Purpose

Make a missing portion of optional project context visible to operators and LLM
consumers. At baseline `59dcc7a65f04de5cb31f4caa99df157697875058`, the standalone executor caught
all exceptions during project metrics collection without recording a diagnostic.
Doctor detected both the per-file catch and the outer fallback.

<!-- docs:section scope -->
## Scope

This document describes `StrategyExecutor._get_project_metrics` and the prompt
it supplies to the standalone executor. The source revision identifies the
independently merged implementation. Version 1 remains available at that immutable
revision. Publication and runtime deployment have separate observed evidence below.

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

## Version 2 — deployed acceptance, 2026-09-10 Europe/Warsaw

The independent Validator merged PR #62 at `51b0c94f01d78a0d82ff92b998114e5ae6b9fffa`.
The required `ci-loop` and `notify` checks passed, as did the locked Python 3.10
and 3.13 test jobs. Deployment was an operator action under session authorization;
these receipts do not claim autonomous repair admission.

The active `subactor-platform-planfile-1` now uses image
`sha256:d96361f68299e4af1838a2a8d2020a82cc1c5afc5efbc86b1dd59cfdeb0c4a8a`.
This image replaces only `executor_standalone.py` in the prior runtime image
`sha256:68ada5703c25c6b3847fa7e0807e94e64ad17570a3594cb0059aa9d701803faa`;
it is not a claim that the complete installed package equals the merged source.
The installed module SHA-256 is
`04d61f336cd2792ba13dfb169bfa7bd4fe7486ebac45da04e71f398efce8f952`.

Observed acceptance:

- Six regression tests from the protected source passed inside the candidate
  image without network access or production data volumes.
- The replacement became healthy in 11.2 seconds. Live configuration, host
  settings, mount bindings and network membership matched the prior container.
- The installed module returned partial metrics for invalid encoding, marked
  the LLM prompt as incomplete, reported filesystem failures without exception
  payloads, and propagated unexpected programming errors from the collector.
- HTTP `/health` returned `ok` in 0.010 seconds. An existing deployment ticket
  read returned in 0.111 seconds. These are individual observations, not an SLA.
- The published Doctor analyzer from revision
  `775935b40dbe6020f3a0aa10fe81d6cfca6ac954` found zero matching issues in the
  installed module, compared with two in the previous source.

The previous container is retained, stopped, as
`subactor-platform-planfile-1-rollback-metrics-51b0c94`. No data volume was replaced.
Private recovery storage contains the exact previous Docker configuration and
the deployment plan. The durable image override is
`~/.local/share/subactor/planfile/releases/metrics-51b0c94f01d78a0d82ff92b998114e5ae6b9fffa/compose.image.json`.
Use that override when intentionally recreating this release through Compose.
The previous container's labels reference a missing temporary Compose override;
those historical labels were preserved, not treated as a complete restoration
recipe. Recovery uses the retained container and privately captured live binding.

The dirty primary source checkout was preserved. Consequently, Search may still
observe the older checkout revision even though the approved module is deployed;
the runtime recheck above is a separate observation. Archive data, credentials,
raw logs and full configuration are excluded from this document.

The bounded acceptance receipt stored with PLF-13798 has SHA-256
`da8ae3972a729ec9ca2aedc5684f539b9586d77439fa1039cce35edc1ce9f794`.
