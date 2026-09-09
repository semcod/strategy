---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "ci-cd-integration",
  "kind": "information",
  "version": 1,
  "title": "Current Planfile CI integration",
  "status": "proposed",
  "owner": "semcod/planfile",
  "created": "2026-09-09",
  "updated": "2026-09-09",
  "review_after": "2026-10-09",
  "source_revision": "53754107b59a4457264632e1aa53aa8fc9491717",
  "affected_repositories": [
    "semcod/planfile"
  ],
  "evidence": [
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/docs/CI_CD_INTEGRATION.md",
    "https://github.com/semcod/planfile/blob/53754107b59a4457264632e1aa53aa8fc9491717/.github/workflows/ci-auto-loop.yml"
  ]
}
---

# Current Planfile CI integration

<!-- docs:section purpose -->
## Purpose

Describe committed CI gates and the optional auto-loop. Historical pseudocode
must not be mistaken for current executable behavior.

<!-- docs:section scope -->
## Scope

The [workflow source](../../.github/workflows/ci-auto-loop.yml) owns exact triggers,
permissions, secret references and command syntax. The [Python API](python-api.md)
owns the runner contract. This document changes no workflow or publication policy.

<!-- docs:section evidence -->
## Evidence

The workflow runs deterministic pytest before the optional auto-loop. AUTO_FIX
and UPDATE_STRATEGY default to false. The historical guide used removed helpers
and old flags; the [current CLI](../../planfile/cli/groups/auto/commands.py) takes
strategy and project as positional arguments.

<!-- docs:section content -->
## Local verification and invocation

```bash
pytest -q --junitxml=test-results.xml --cov=planfile --cov-report=json:coverage.json
planfile auto loop --help
```

The separate [locked tests](../../.github/workflows/test-locked.yml) declare Python
3.10 and 3.13. Passing a local interpreter does not establish that matrix.
After providing a valid strategy and selecting an authorized project:

```bash
planfile auto loop ./strategy.yaml . --max-iterations 5 --dry-run --output ci-results.json
```

The loop runs tests and analysis. Constructing its runner may initialize local
Planfile state, so dry-run is not a general no-write sandbox. Backend effects and
automatic fixes require their corresponding explicit configuration. A green test
or this example grants no authority to create remote issues, apply patches,
publish code or close work.

The workflow enables the auto-loop and Ollama setup only when AUTO_FIX is true.
Its strategy-update branch separately requires failure and UPDATE_STRATEGY.
Consult the workflow for artifact-upload and notification conditions instead of
copying obsolete YAML into another repository.

<!-- docs:section limitations -->
## Limits

This verifies source, not a live hosted run, external notifications or production
deployment. OneDev and Validator adoption must preserve required tests and actor
boundaries. Credentials and backend availability remain runtime prerequisites.

<!-- docs:section next_actions -->
## Maintenance

Update this version when CLI arguments or workflow conditions change. Bind actual
execution receipts before claiming deployed success.
