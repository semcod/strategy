# ticket-061 — Observable executor metrics failures

Intent: retain best-effort project metrics for expected read failures, report
incomplete file-read coverage in diagnostics and LLM context, and stop swallowing
unexpected programming errors in the metrics collector.

Inputs: [Doctor #377](https://github.com/subactor/doctor-agent/issues/377),
[Doctor #378](https://github.com/subactor/doctor-agent/issues/378).

Acceptance: regression tests cover invalid encoding, denied reads, enumeration
failure, unexpected errors, successful reads and partial LLM context. Run the
existing test suite and repository-required checks before independent publication.

Canonical result: [Executor metrics diagnostics](../../docs/information/executor-metrics.md).
