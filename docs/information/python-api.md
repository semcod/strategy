---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "python-api",
  "kind": "information",
  "version": 2,
  "title": "Current Planfile Python API",
  "status": "proposed",
  "owner": "semcod/planfile",
  "created": "2026-09-09",
  "updated": "2026-09-10",
  "review_after": "2026-10-10",
  "source_revision": "cde0727646c006845278d4774c06718cf7e9d148",
  "affected_repositories": [
    "semcod/planfile"
  ],
  "evidence": [
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/planfile/__init__.py",
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/planfile/ci.py",
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/planfile/loaders/yaml_loader.py",
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/docs/API.md",
    "https://github.com/semcod/planfile/blob/cde0727646c006845278d4774c06718cf7e9d148/planfile/strategy_input.py",
    "https://github.com/semcod/planfile/blob/cde0727646c006845278d4774c06718cf7e9d148/tests/test_strategy_input.py"
  ]
}
---

# Current Planfile Python API

<!-- docs:section purpose -->
## Purpose

Provide importable entry points and the actual CI runner contract. This replaces
the old API reference, which mixed current ticket APIs with removed modules and
unimplemented example methods. The prior text remains available through the
immutable Git URL in metadata.

<!-- docs:section scope -->
## Scope

This reference binds the committed source revision above. Local unpublished
changes and external deployments are outside that binding. Maintained automation
contracts are documented in [Public automation contracts](../PUBLIC_CONTRACTS.md).
The generated `docs/README.md` is a historical analysis snapshot, not the public
CLI/API contract.

<!-- docs:section evidence -->
## Evidence and choice of source

The July 21 documentation commit changed agent repository names; it did not
update the CI runner examples. The implemented runner was already in
`planfile/ci.py` on July 20. Therefore the document's newer commit timestamp does
not justify restoring the removed `ci_runner` module or inventing its former
methods. The source signatures and existing CI tests determine this correction.

<!-- docs:section content -->
## Public facade and models

```python
from planfile import Planfile, Strategy, Sprint, Task, Ticket, TicketStatus
```

`Planfile(project_path=".")` opens a store and initializes it when missing.
`Planfile.auto_discover(start_path=".")` searches for a parent `.planfile` and
initializes at the starting path when none exists. Both can write project state;
constructing the facade is not a read-only probe. Use a disposable directory for
examples and tests. Ticket proposals and lifecycle mutations retain the separate
contracts and authorization boundaries linked above.

## YAML loaders

```python
from planfile.loaders.yaml_loader import (
    load_strategy_yaml,
    save_strategy_yaml,
    load_tasks_yaml,
    validate_strategy_schema,
)

strategy = load_strategy_yaml("strategy.yaml")
issues = validate_strategy_schema("strategy.yaml")
```

`load_strategy_yaml(path)` returns the typed Strategy after legacy-shape
normalization. Invalid input raises `ValueError` with formatted validation
errors. `save_strategy_yaml(strategy_or_dict, path)` writes YAML; it does not
execute the strategy. `load_tasks_yaml(path)` reads task-pattern groups.
The old `load_strategy` and `save_strategy` names are not loader exports.

## Ticket validation and TODO synchronization

`validate_planfile_tickets(strategy_path, project_path)` and
`sync_todo_checkboxes_from_planfile(strategy_path, project_path)` require a
readable UTF-8 YAML mapping. An explicit empty mapping (`{}`) is valid; an empty
file or a YAML sequence is not.

Both functions raise `ValueError` when loading fails, with one of these stable
messages: `strategy_input_unreadable`, `strategy_input_invalid_encoding`,
`strategy_input_invalid_yaml`, or `strategy_input_not_mapping`. These messages
omit YAML contents. Callers must surface the failure or request corrected input;
they must not treat it as a successful report with zero tickets.

TODO synchronization validates input before processing execution results or
writing checkboxes, including when `enabled=True` is supplied explicitly.
Previously these input failures silently became an empty strategy.

## CI runner

```python
from planfile.ci import CIRunner, TestResult, BugReport

runner = CIRunner(
    strategy_path="strategy.yaml",
    project_path=".",
    backends={},
    max_iterations=5,
    auto_fix=False,
    dry_run=True,
)
```

Construction loads the strategy and may discover/initialize a Planfile store.
The constructor accepts backend instances in a dictionary, not backend-name
strings. Its default `auto_fix` is **False** and default `dry_run` is **False**;
the example selects a dry run explicitly. Running the loop invokes configured
tests/analysis and can create tickets. `dry_run` is not a general side-effect
sandbox for construction or every loop stage.

| Method | Result or effect |
| --- | --- |
| `run_tests()` | `TestResult`: passed, failed_tests, coverage, metrics and output |
| `run_code_analysis()` | Analysis dictionary from the configured analysis command |
| `generate_bug_report(test_result, metrics)` | `BugReport`: name, description, files, test_names and severity |
| `create_bug_tickets(bug_report)` | Creates tickets and returns their identifiers |
| `run_loop()` | Executes the configured bounded loop and returns a result dictionary |
| `save_results(results, output_path=None)` | Writes results to a JSON file |

`BugAnalyzer`, `run_auto_loop()` and `run_iteration()` are not current public
classes/methods. CLI commands are registered through the groups under
`planfile.cli.groups`; `auto_loop_cli` is not exported by `planfile.cli.commands`.
Use `planfile --help` to inspect the installed CLI rather than importing a
historical handler name.

## Logging and credentials

Use Python's standard `logging` configuration for application logging.
`planfile.utils.setup_logging`, `planfile.utils.secure.get_token` and
`planfile.utils.secure.mask_token` are not current exports. Backend-specific
configuration owns credentials; this reference does not introduce a substitute
secret manager or suggest logging token values.

<!-- docs:section limitations -->
## Validation limits

The imports, signatures and example syntax are checked against the bound source.
No external backend, test runner, LLM call or ticket mutation is exercised by
this documentation verification. Tutorial placeholders and proposed architecture
must not be treated as evidence that an API exists.

<!-- docs:section next_actions -->
## Maintenance

Update this canonical document and increment its declared version when an API
changes. Keep generated snapshots distinct from maintained usage guidance.
