# Generated Planfile reference

Current maintained [Python API](information/python-api.md).
Optional executor context: [metrics diagnostics](information/executor-metrics.md).

For maintained documentation navigation, start with
[`NAVIGATION.md`](information/navigation.md). The content below is a generated
source-analysis snapshot and may be refreshed by code2docs.

<!-- code2docs:start -->
# planfile

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.10-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-644-green)
> **644** functions | **75** classes | **177** files | CC̄ = 3.8

> Auto-generated project documentation from source code analysis.

**Author:** Tom Sapletta  
**License:** Apache-2.0[(LICENSE)](LICENSE)
**Repository:** [https://github.com/semcod/planfile](https://github.com/semcod/planfile)

## Installation

### From PyPI

```bash
pip install planfile
```

### From Source

```bash
git clone https://github.com/semcod/planfile
cd planfile
pip install -e .
```

### Optional Extras

```bash
pip install planfile[github]    # github features
pip install planfile[jira]    # jira features
pip install planfile[gitlab]    # gitlab features
pip install planfile[litellm]    # litellm features
pip install planfile[openai]    # openai features
pip install planfile[anthropic]    # anthropic features
pip install planfile[llx]    # llx features
pip install planfile[all]    # all optional features
pip install planfile[dev]    # development tools
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
planfile ./my-project

# Only regenerate README
planfile ./my-project --readme-only

# Preview what would be generated (no file writes)
planfile ./my-project --dry-run

# Check documentation health
planfile check ./my-project

# Sync — regenerate only changed modules
planfile sync ./my-project
```

### Python API

```python
from planfile import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `planfile`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `planfile.yaml` in your project root (or run `planfile init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

planfile can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- planfile:start -->
# Project Title
... auto-generated content ...
<!-- planfile:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
planfile/
├── cleanup_redundant├── project├── auto_generate_planfile├── docker-entrypoint├── run_examples    ├── run    ├── run_all_tests    ├── validate_with_llx        ├── run        ├── test_interactive_expect        ├── run        ├── run_all        ├── run        ├── run        ├── 01_start_server        ├── run        ├── run        ├── run        ├── run        ├── ci-workflow        ├── run        ├── run        ├── run        ├── 02_curl_examples        ├── run_all        ├── 01_full_workflow        ├── 04_javascript_client        ├── run        ├── planfile-sync        ├── run        ├── run        ├── run_fixed        ├── test_readme_examples        ├── run_fixed        ├── run        ├── verify_planfile        ├── run        ├── test_planfile_generation        ├── demo    ├── examples├── mcp-server-example    ├── execution├── planfile/    ├── runner        ├── 01_basic_usage    ├── models        ├── state        ├── 02_mcp_integration    ├── sync/        ├── 04_analytics_simple    ├── ci        ├── utils        ├── 03_integration        ├── 04_llx_integration        ├── 03_integration_simple        ├── markdown_backend/            ├── files        ├── operations        ├── 04_advanced_filtering        ├── 02_ticket_management            ├── constants        ├── cli_loader            ├── tickets    ├── loaders/        ├── yaml_loader    ├── analysis/        ├── generator    ├── llx_validator        ├── file_analyzer        ├── generators/            ├── metrics_extractor    ├── server_common        ├── parsers/        ├── 03_python_client        ├── sprint_generator        ├── external_tools        ├── store    ├── core/            ├── text_parser        ├── models/        ├── store_files            ├── json_parser    ├── PROPOSED_API_IMPROVEMENTS            ├── yaml_parser        ├── store_tickets        ├── models            ├── toon_parser        ├── common        ├── yaml_importer    ├── importers/        ├── json_importer        ├── 03_proxy_routing        ├── auto_loop        ├── commands        ├── extra_commands        ├── project_detector/        ├── __main__    ├── cli/        ├── redup_importer            ├── sync/                ├── commands            ├── review/                ├── commands                ├── core            ├── health/                ├── utils                ├── commands            ├── examples/            ├── query/                ├── commands            ├── apply/                ├── commands        ├── code2llm_importer                ├── utils            ├── init/            ├── auto/        ├── vallm_importer            ├── generate/            ├── base                ├── commands            ├── ticket/            ├── validate/                ├── commands                ├── commands                ├── commands                ├── commands            ├── errors            ├── registry            ├── console        ├── core/            ├── fallback            ├── progress            ├── readme            ├── license            ├── structure            ├── package            ├── git            ├── model_tier            ├── pyproject            ├── gates            ├── main            ├── inference    ├── llm/        ├── prompts        ├── client        ├── generator        ├── adapters    ├── utils/    ├── extensions/    ├── mcp/        ├── priorities    ├── executor_standalone            ├── base                ├── commands    ├── integrations/        ├── metrics        ├── server        ├── config    ├── api/            ├── backend        ├── gitlab        ├── base        ├── generic        ├── gitlab        ├── jira        ├── generic        ├── github        ├── mock        ├── base        ├── github            ├── ticket            ├── strategy        ├── server        ├── jira```

## API Overview

### Classes

- **`UserType`** — —
- **`User`** — —
- **`UserService`** — —
- **`UserController`** — —
- **`PlanfileClient`** — —
- **`TestClass`** — —
- **`User`** — —
- **`UserController`** — —
- **`Config`** — —
- **`UserService`** — —
- **`Planfile`** — Main entry point — convenience wrapper around PlanfileStore.
- **`SyncState`** — Persist mapping between local ticket IDs and remote IDs.
- **`TestResult`** — Result of running tests.
- **`BugReport`** — Generated bug report from test failures.
- **`CIRunner`** — CI/CD runner with automated bug-fix loop and ticket creation.
- **`TicketLogger`** — Logger that creates tickets for errors and warnings.
- **`ProjectMetrics`** — Project metrics from LLX analysis.
- **`LLXIntegration`** — Integration with LLX for code analysis and model selection.
- **`MarkdownFileManager`** — File existence and bootstrap helpers for markdown ticket files.
- **`MarkdownTicketHelpers`** — Ticket routing, lookup, formatting, and persistence helpers.
- **`PlanfileGenerator`** — Generate comprehensive planfile from file analysis.
- **`LLXValidator`** — Use LLX to validate generated code and strategies.
- **`FileAnalyzer`** — Analyzes YAML/JSON files to extract issues and metrics.
- **`PlanfileClient`** — Python client for planfile REST API.
- **`SprintGenerator`** — Generates sprints and tickets from extracted information.
- **`AnalysisResults`** — Results from external tool analysis.
- **`ExternalToolRunner`** — Runner for external code analysis tools.
- **`Store`** — —
- **`StoreFileMixin`** — —
- **`TicketLogger`** — Native ticket logging - replaces 80-line example.
- **`PlanfileStoreExtended`** — Extended store with analytics and export.
- **`TicketStoreMixin`** — —
- **`ExtractedIssue`** — Represents an issue extracted from a file.
- **`ExtractedMetric`** — Represents a metric extracted from a file.
- **`ExtractedTask`** — Represents a task extracted from a file.
- **`ProxyClient`** — Client for interacting with Proxym API.
- **`EvolutionParser`** — State machine parser for evolution.toon NEXT[] sections.
- **`VallmParser`** — Parser for vallm validation.toon files.
- **`TaskType`** — Type of task in the planfile.
- **`ModelTier`** — Model tier for different phases of work.
- **`TicketStatus`** — Status of a ticket.
- **`CommandRegistry`** — Registry for CLI command groups.
- **`LLMTestResult`** — —
- **`BaseLLMAdapter`** — —
- **`LiteLLMAdapter`** — —
- **`OpenRouterAdapter`** — —
- **`LocalLLMAdapter`** — —
- **`LLMTestRunner`** — —
- **`TicketLogger`** — Logger that creates tickets for errors, warnings, and alerts.
- **`TaskResult`** — Result of executing a task.
- **`LLMClient`** — Simple LLM client interface.
- **`StrategyExecutor`** — Standalone strategy executor.
- **`DetectedQualityGate`** — Detected quality gate from project files.
- **`DetectedProject`** — Container for detected project information.
- **`IntegrationConfig`** — Manages integration configuration with support for multiple config files.
- **`MarkdownFileBackend`** — Backend for managing tickets in CHANGELOG.md and TODO.md files.
- **`TicketRef`** — Reference to a created/updated ticket.
- **`TicketStatus`** — Status of a ticket.
- **`PMBackend`** — Protocol for PM system backends.
- **`BasePMBackend`** — Base class for PM backends with common functionality.
- **`GenericBackend`** — Generic HTTP API backend for PM systems.
- **`GitLabBackend`** — GitLab Issues integration backend.
- **`JiraBackend`** — Jira integration backend.
- **`MockBackend`** — Mock backend for examples and testing that doesn't require any credentials.
- **`GitHubBackend`** — GitHub Issues integration backend.
- **`TicketSource`** — Who/what created the ticket.
- **`Ticket`** — Atomic unit of work in planfile.
- **`ModelHints`** — AI model hints for different phases of task execution.
- **`Task`** — A task in a sprint - simplified and directly embedded.
- **`Sprint`** — A sprint in the planfile.
- **`QualityGate`** — Quality gate definition.
- **`Goal`** — Project goal definition.
- **`Strategy`** — Main strategy configuration - simplified and more flexible.
- **`TicketCreate`** — —
- **`TicketUpdate`** — —

### Functions

- `check_env()` — —
- `validate_config()` — —
- `setup_workspace()` — —
- `run_command()` — —
- `main()` — —
- `print_header()` — —
- `print_step()` — —
- `print_success()` — —
- `print_error()` — —
- `print_info()` — —
- `run_example()` — —
- `check_prerequisites()` — —
- `setup_environment()` — —
- `run_all_examples()` — —
- `run_specific_example()` — —
- `show_usage()` — —
- `list_examples()` — —
- `main()` — —
- `run_test()` — —
- `run_python_test()` — —
- `validate_file()` — —
- `print()` — —
- `cleanup()` — —
- `print()` — —
- `print()` — —
- `print_step()` — —
- `print()` — —
- `create_user()` — —
- `get_user()` — —
- `update_user()` — —
- `setattr()` — —
- `delete_user()` — —
- `get_users_by_type()` — —
- `authenticate()` — —
- `export_to_json()` — —
- `import_from_json()` — —
- `get_statistics()` — —
- `BASE_URL()` — —
- `print()` — —
- `hello_world()` — —
- `greet()` — —
- `validate_planfile()` — —
- `print()` — —
- `test_planfile_generation()` — —
- `to_dict()` — —
- `render_user()` — —
- `create_user()` — —
- `health_check()` — —
- `get_user()` — —
- `demo_checkbox_tickets()` — Demonstrate checkbox ticket parsing and manipulation.
- `example_create_strategy()` — Create a strategy using LLX with local LLM.
- `example_validate_strategy()` — Load and validate an existing strategy.
- `example_run_strategy()` — Run strategy to create tickets (dry run).
- `example_verify_strategy()` — Verify strategy execution.
- `example_programmatic_strategy()` — Create strategy programmatically without LLM.
- `planfile_generate(arguments)` — —
- `planfile_apply(arguments)` — —
- `planfile_review(arguments)` — —
- `main()` — —
- `quick_ticket(title, tool)` — One-liner ticket creation for tools.
- `load_valid_strategy(path)` — Load and validate strategy from YAML file.
- `verify_strategy_post_execution(strategy, project_path, backend)` — Verify strategy after execution.
- `analyze_project_metrics(project_path)` — Analyze project metrics using available tools.
- `apply_strategy_to_tickets(strategy, project_path, backend, dry_run)` — Apply strategy to create tickets in PM system.
- `review_strategy(strategy, project_path, backends, backend_name)` — Review strategy execution by checking ticket statuses.
- `run_strategy(strategy_path, project_path, backend, dry_run)` — Run strategy: load, validate, and apply.
- `example_1_basic_initialization()` — Initialize planfile with auto-discovery.
- `example_2_create_ticket()` — Create a ticket programmatically.
- `example_3_quick_ticket()` — Use quick_ticket helper for one-off ticket creation.
- `example_4_list_tickets()` — List and filter tickets.
- `main()` — Run all examples.
- `run_mcp_tool(tool_name, arguments)` — Simulate running an MCP tool.
- `simulate_planfile_generate(args)` — Simulate planfile generate tool.
- `simulate_planfile_apply(args)` — Simulate planfile apply tool.
- `simulate_planfile_review(args)` — Simulate planfile review tool.
- `example_mcp_session()` — Example of an LLM agent using planfile MCP tools.
- `create_mcp_tool_definitions()` — Create MCP tool definitions for integration.
- `main()` — Run simplified analytics examples.
- `save_v1_format(file_path, data)` — Save data back to v1 format YAML file.
- `example_cli_tool_integration()` — Show integration with a CLI tool.
- `example_monitoring_integration()` — Monitoring system integration.
- `example_ci_pipeline_integration()` — CI pipeline failure tracking.
- `example_custom_decorator()` — Decorator for automatic error tracking.
- `main()` — Run all examples.
- `example_metric_driven_planning()` — Example: Generate strategy based on actual project metrics.
- `create_llx_config_example()` — Create example LLX configuration for planfile integration.
- `main()` — Run simplified integration examples.
- `sync_to_external(backend, tickets, dry_run, store)` — Sync planfile tickets to external system.
- `sync_from_external(backend, store, dry_run, integration_name)` — Sync tickets from external system to planfile.
- `example_basic_filtering()` — Basic ticket filtering.
- `example_combined_filters()` — Combined filter criteria.
- `example_search_by_labels()` — Search by labels and tags.
- `example_export_filtered()` — Export filtered results to various formats.
- `example_statistics()` — Generate ticket statistics.
- `main()` — Run all examples.
- `example_create_tickets()` — Create multiple tickets.
- `example_read_tickets(ticket_ids)` — Read/retrieve tickets.
- `example_update_tickets(ticket_ids)` — Update ticket properties.
- `example_bulk_operations()` — Bulk create tickets from external data.
- `example_delete_and_move(ticket_ids)` — Delete and move tickets.
- `main()` — Run all examples.
- `load_from_json(file_path)` — Load JSON file and return as dictionary.
- `save_to_json(data, file_path)` — Save dictionary to JSON file.
- `load_strategy_from_json(file_path)` — Load strategy from JSON file.
- `save_strategy_to_json(strategy, file_path)` — Save strategy to JSON file.
- `export_results_to_markdown(results, file_path)` — Export strategy results to Markdown file.
- `load_yaml(file_path)` — Load YAML file and return as dictionary.
- `save_yaml(data, file_path)` — Save dictionary to YAML file.
- `load_strategy_yaml(file_path)` — Load strategy from YAML file.
- `save_strategy_yaml(strategy, file_path)` — Save strategy to YAML file.
- `load_tasks_yaml(file_path)` — Load task patterns from YAML file.
- `merge_strategy_with_tasks(strategy, tasks_file)` — Merge additional task patterns into a planfile.
- `validate_strategy_schema(file_path)` — Validate strategy YAML file and return list of issues.
- `create_validation_script()` — Create a validation script that uses LLX.
- `extract_key_metrics(analysis_result, external_metrics)` — Extract key metrics from analysis.
- `get_planfile(start_path)` — Return a cached Planfile instance discovered from the project tree.
- `example_basic_operations(client)` — Basic CRUD operations.
- `example_bulk_operations(client)` — Bulk create and list.
- `example_workflow(client, ticket_id)` — Complete ticket workflow.
- `example_error_handling(client)` — Handle API errors gracefully.
- `main()` — Run all examples.
- `run_external_analysis(project_path)` — Convenience function to run all external tools.
- `analyze_text(file_path)` — Analyze text content for TODOs, FIXMEs, and metrics.
- `analyze_json(file_path)` — Analyze JSON file.
- `extract_from_yaml_structure(data, path, parent_key, visited)` — Extract issues from YAML structure with recursion protection.
- `analyze_yaml(file_path)` — Analyze YAML file with better error handling.
- `analyze_toon(file_path)` — Analyze Toon format files with enhanced parsing.
- `normalize_ticket_dict(item)` — Ensure minimal ticket fields exist.
- `load_structured_tickets(path, loader)` — Load tickets from JSON/YAML-like structured data.
- `import_yaml(path)` — Parse a YAML file containing ticket data.
- `register_importer(name, importer_cls)` — —
- `import_from_source(path, source)` — Auto-detect format and import tickets.
- `import_json(path)` — Parse a JSON file containing ticket data.
- `example_strategy_generation_with_proxy()` — Example: Generate strategy using proxy for smart model routing.
- `create_proxy_config_example()` — Create example proxy configuration for planfile integration.
- `example_budget_tracking()` — Example: Budget tracking with proxy.
- `create_auto_app()` — Create the auto command app (legacy compatibility).
- `version_callback(value)` — —
- `main_callback(version)` — —
- `main()` — Main CLI entry point.
- `add_extra_commands(app)` — Add health and examples command groups to the CLI app.
- `import_redup(file_path)` — Import duplication issues from redup toon.yaml file.
- `register_sync_commands(app)` — Register all sync commands with the main CLI app.
- `github_cmd(directory, dry_run, direction)` — Sync tickets with GitHub Issues.
- `gitlab_cmd(directory, dry_run, direction)` — Sync tickets with GitLab Issues.
- `jira_cmd(directory, dry_run, direction)` — Sync tickets with Jira.
- `markdown_cmd(directory, dry_run, direction)` — Sync tickets with markdown files (CHANGELOG.md, TODO.md).
- `all_cmd(directory, dry_run, direction)` — Sync tickets with all configured integrations.
- `register_review_commands(app)` — Register review subcommand on the typer app.
- `review_strategy_cli(strategy_path, project_path, backend, config_file)` — Review strategy execution and progress.
- `sync_integration(integration_name, directory, dry_run, direction)` — Sync with a specific integration.
- `register_health_commands(app)` — Register health commands on the typer app.
- `get_backend(backend_type, config)` — Get backend instance by type and config.
- `create_health_app()` — Create and return the health sub-app.
- `register_examples_commands(app)` — Register examples commands on the typer app.
- `register_query_commands(app)` — Register all query commands with the main CLI app.
- `execute_apply_strategy(strategy, project_path, backend, dry_run)` — Execute strategy application with progress bar.
- `display_apply_results(results)` — Display strategy application results.
- `save_results(results, output)` — Save results to file if specified.
- `apply_strategy_cli(strategy_path, project_path, backend, config_file)` — Apply a strategy to create tickets.
- `register_apply_commands(app)` — Register apply subcommand on the typer app.
- `create_examples_app()` — Create and return the examples sub-app.
- `import_code2llm(toon_path, auto_priority, sprint)` — Parse evolution.toon NEXT[] → ticket dicts.
- `get_backend(backend_type, config)` — Get backend instance by type and config.
- `load_and_validate_strategy(strategy_path)` — Load and validate strategy file.
- `load_backend_config(backend, config_file)` — Load backend configuration from file or environment.
- `parse_sprint_filter(sprint_filter)` — Parse sprint filter from string.
- `select_backend(backend, backend_config)` — Select and initialize backend.
- `register_init_commands(app)` — Register init subcommand on the typer app.
- `register_auto_commands(app)` — Register auto subcommands on the typer app.
- `import_vallm(toon_path, auto_priority)` — Parse vallm validation.toon ERRORS[] → ticket dicts.
- `register_generate_commands(app)` — Register generate subcommands on the typer app.
- `generate_strategy_cli(project_path, output, model, sprints)` — Generate strategy.yaml from project analysis + LLM.
- `generate_from_files_cmd(project_path, output, project_name, max_sprints)` — Generate planfile from file analysis (no LLM required).
- `register_ticket_commands(app)` — Register ticket subcommands on the typer app.
- `register_validate_commands(app)` — Register validate subcommand on the typer app.
- `validate_strategy_cli(strategy_path, verbose)` — Validate a strategy YAML file.
- `init_strategy_cli(output, yes)` — Interactive wizard — creates a strategy by asking questions.
- `calculate_strategy_stats(strategy)` — Calculate statistics for a strategy.
- `stats_cmd(strategy_file)` — Show strategy statistics.
- `compare_strategies(s1, s2)` — Compare two strategies and return differences.
- `compare_cmd(strategy1, strategy2, output)` — Compare two strategies.
- `export_cmd(strategy_file, format, output)` — Export strategy to various formats.
- `merge_cmd(strategy_files, output, name)` — Merge multiple strategies into one.
- `get_backend(backend_type)` — Get backend instance by type.
- `auto_loop_cmd(strategy, project_path, backend, max_iterations)` — Run automated CI/CD loop: test → ticket → fix → retest.
- `ci_status_cmd(project_path)` — Check current CI status without running tests.
- `exit_with_error(message, code)` — Print error message and exit with code.
- `exit_with_warning(message, code)` — Print warning message and exit with code.
- `handle_exception(e, context)` — Handle exception with optional context.
- `register_simple_command(app, name, command, help_text)` — Register a simple single command on the typer app.
- `register_typer_group(app, name, factory, help_text)` — Register a sub-typer group on the main app.
- `print_success(message)` — Print a success message.
- `print_error(message)` — Print an error message.
- `print_warning(message)` — Print a warning message.
- `print_info(message)` — Print an info message.
- `print_dim(message)` — Print a dimmed message.
- `with_spinner(description, fn)` — Execute function with a spinner progress indicator.
- `create_progress()` — Create a standard progress bar instance.
- `detect_project(project_path)` — Auto-detect project information from various sources.
- `get_detected_values()` — Get detected project values as a dictionary for use in CLI.
- `build_strategy_prompt(metrics, sprints, focus)` — Build a structured prompt for strategy generation.
- `call_llm(prompt, model, temperature)` — Call LLM via LiteLLM. Falls back to llx proxy if available.
- `generate_strategy(project_path)` — Generate a complete strategy from project analysis.
- `calculate_task_priority(base_priority, task_type, sprint_id, weight_factors)` — Calculate task priority based on type, sprint, and base priority.
- `map_priority_to_system(priority, system)` — Map generic priority to system-specific priority.
- `get_priority_color(priority)` — Get color code for priority (for UI display).
- `create_openai_client(api_key, model)` — Create an OpenAI client.
- `create_litellm_client(api_key, model)` — Create a LiteLLM client.
- `execute_strategy(strategy_path, project_path)` — Execute strategy from file - convenience function.
- `ticket_create(title, priority, sprint, source)` — Create a new ticket.
- `ticket_list(sprint, status, source, label)` — List tickets with optional filters.
- `ticket_show(ticket_id, fmt)` — Show details of a single ticket.
- `ticket_update(ticket_id, status, priority, title)` — Update ticket fields.
- `ticket_move(ticket_id, to_sprint)` — Move ticket to another sprint.
- `ticket_import(source, sprint, from_file)` — Import tickets from tool output (stdin JSON or file).
- `ticket_done(ticket_id)` — Mark ticket as done (shortcut for update --status done).
- `ticket_start(ticket_id)` — Mark ticket as in_progress (shortcut for update --status in_progress).
- `ticket_block(ticket_id, reason)` — Mark ticket as blocked (shortcut for update --status blocked).
- `ticket_review(ticket_id)` — Mark ticket as ready for review (shortcut for update --status review).
- `ticket_import_todo(todo_file, sprint, dry_run)` — Import tickets from TODO.md checkbox items into planfile.
- `ticket_export_todo(todo_file, sprint, include_done)` — Export planfile tickets to TODO.md format.
- `analyze_project_metrics(project_path)` — Analyze project metrics for strategy review.
- `calculate_strategy_health(strategy_results)` — Calculate health metrics for a strategy execution.
- `handle_tool_call(name, arguments)` — Dispatch an MCP tool call and return the result dict.
- `main()` — Run a minimal MCP stdio server.
- `list_tickets(sprint, status)` — —
- `create_ticket(body)` — —
- `get_ticket(ticket_id)` — —
- `update_ticket(ticket_id, body)` — —
- `delete_ticket(ticket_id)` — —
- `move_ticket(ticket_id, to_sprint)` — —
- `health()` — —


## Project Structure

📄 `auto_generate_planfile`
📄 `cleanup_redundant`
📄 `docker-entrypoint` (5 functions)
📄 `examples.PROPOSED_API_IMPROVEMENTS` (7 functions, 2 classes)
📄 `examples.advanced-usage.ci-workflow`
📄 `examples.advanced-usage.run`
📄 `examples.bash-generation.test_planfile_generation` (10 functions, 4 classes)
📄 `examples.bash-generation.verify_planfile` (4 functions)
📄 `examples.checkbox-tickets.demo` (1 functions)
📄 `examples.checkbox-tickets.run`
📄 `examples.cli-commands.run`
📄 `examples.cli-commands.run_fixed`
📄 `examples.code2llm.run`
📄 `examples.comprehensive-example.run`
📄 `examples.demo-without-keys.run`
📄 `examples.ecosystem.01_full_workflow` (17 functions, 6 classes)
📄 `examples.ecosystem.02_mcp_integration` (6 functions)
📄 `examples.ecosystem.03_proxy_routing` (7 functions, 1 classes)
📄 `examples.ecosystem.04_llx_integration` (9 functions, 2 classes)
📄 `examples.external-tools.run`
📄 `examples.github.planfile-sync`
📄 `examples.github.run` (7 functions)
📄 `examples.gitlab.run` (7 functions)
📄 `examples.integrated-functionality.run`
📄 `examples.interactive-tests.test_interactive_expect`
📄 `examples.jira.run` (9 functions)
📄 `examples.llm-integration.run`
📄 `examples.llx_validator` (7 functions, 1 classes)
📄 `examples.multi-ticket.run` (8 functions)
📄 `examples.python-api.01_basic_usage` (5 functions)
📄 `examples.python-api.02_ticket_management` (6 functions)
📄 `examples.python-api.03_integration` (9 functions, 1 classes)
📄 `examples.python-api.03_integration_simple` (1 functions)
📄 `examples.python-api.04_advanced_filtering` (6 functions)
📄 `examples.python-api.04_analytics_simple` (1 functions)
📄 `examples.python-api.run_all`
📄 `examples.quick-start.run`
📄 `examples.quick-start.run_fixed`
📄 `examples.readme-tests.test_readme_examples` (3 functions, 1 classes)
📄 `examples.redup.run`
📄 `examples.rest-api.01_start_server`
📄 `examples.rest-api.02_curl_examples` (2 functions)
📄 `examples.rest-api.03_python_client` (14 functions, 1 classes)
📄 `examples.rest-api.04_javascript_client` (22 functions, 1 classes)
📄 `examples.rest-api.run_all` (1 functions)
📄 `examples.run`
📄 `examples.run_all_tests` (2 functions)
📄 `examples.validate_with_llx` (1 functions)
📄 `examples.vallm.run`
📄 `mcp-server-example` (4 functions)
📦 `planfile` (9 functions, 1 classes)
📦 `planfile.analysis`
📄 `planfile.analysis.external_tools` (12 functions, 2 classes)
📄 `planfile.analysis.file_analyzer` (10 functions, 1 classes)
📄 `planfile.analysis.generator` (24 functions, 1 classes)
📦 `planfile.analysis.generators`
📄 `planfile.analysis.generators.metrics_extractor` (6 functions)
📄 `planfile.analysis.models` (3 classes)
📦 `planfile.analysis.parsers`
📄 `planfile.analysis.parsers.json_parser` (1 functions)
📄 `planfile.analysis.parsers.text_parser` (1 functions)
📄 `planfile.analysis.parsers.toon_parser` (7 functions)
📄 `planfile.analysis.parsers.yaml_parser` (7 functions)
📄 `planfile.analysis.sprint_generator` (10 functions, 1 classes)
📦 `planfile.api`
📄 `planfile.api.server` (7 functions, 2 classes)
📄 `planfile.ci` (9 functions, 3 classes)
📦 `planfile.cli`
📄 `planfile.cli.__main__`
📄 `planfile.cli.auto_loop` (1 functions)
📄 `planfile.cli.commands` (3 functions)
📦 `planfile.cli.core`
📄 `planfile.cli.core.console` (5 functions)
📄 `planfile.cli.core.errors` (3 functions)
📄 `planfile.cli.core.progress` (2 functions)
📄 `planfile.cli.core.registry` (5 functions, 1 classes)
📄 `planfile.cli.extra_commands` (1 functions)
📦 `planfile.cli.groups.apply` (1 functions)
📄 `planfile.cli.groups.apply.commands` (4 functions)
📄 `planfile.cli.groups.apply.utils` (5 functions)
📦 `planfile.cli.groups.auto` (1 functions)
📄 `planfile.cli.groups.auto.commands` (8 functions)
📦 `planfile.cli.groups.examples` (1 functions)
📄 `planfile.cli.groups.examples.commands` (3 functions)
📦 `planfile.cli.groups.generate` (1 functions)
📄 `planfile.cli.groups.generate.commands` (2 functions)
📦 `planfile.cli.groups.health` (1 functions)
📄 `planfile.cli.groups.health.commands` (1 functions)
📦 `planfile.cli.groups.init` (1 functions)
📄 `planfile.cli.groups.init.commands` (11 functions)
📦 `planfile.cli.groups.query` (1 functions)
📄 `planfile.cli.groups.query.commands` (8 functions)
📦 `planfile.cli.groups.review` (1 functions)
📄 `planfile.cli.groups.review.commands` (1 functions)
📄 `planfile.cli.groups.review.utils` (3 functions)
📦 `planfile.cli.groups.sync` (1 functions)
📄 `planfile.cli.groups.sync.commands` (5 functions)
📄 `planfile.cli.groups.sync.core` (11 functions)
📦 `planfile.cli.groups.ticket` (1 functions)
📄 `planfile.cli.groups.ticket.commands` (17 functions)
📦 `planfile.cli.groups.validate` (1 functions)
📄 `planfile.cli.groups.validate.commands` (1 functions)
📦 `planfile.cli.project_detector`
📄 `planfile.cli.project_detector.base` (2 classes)
📄 `planfile.cli.project_detector.fallback` (1 functions)
📄 `planfile.cli.project_detector.gates` (13 functions)
📄 `planfile.cli.project_detector.git` (1 functions)
📄 `planfile.cli.project_detector.inference` (3 functions)
📄 `planfile.cli.project_detector.license` (1 functions)
📄 `planfile.cli.project_detector.main` (2 functions)
📄 `planfile.cli.project_detector.model_tier` (4 functions)
📄 `planfile.cli.project_detector.package` (1 functions)
📄 `planfile.cli.project_detector.pyproject` (9 functions)
📄 `planfile.cli.project_detector.readme` (3 functions)
📄 `planfile.cli.project_detector.structure` (1 functions)
📦 `planfile.core`
📦 `planfile.core.models`
📄 `planfile.core.models.base` (3 classes)
📄 `planfile.core.models.strategy` (12 functions, 6 classes)
📄 `planfile.core.models.ticket` (1 functions, 2 classes)
📄 `planfile.core.store` (1 classes)
📄 `planfile.core.store_files` (3 functions, 1 classes)
📄 `planfile.core.store_tickets` (4 functions, 1 classes)
📄 `planfile.examples` (5 functions)
📄 `planfile.execution`
📄 `planfile.executor_standalone` (12 functions, 3 classes)
📦 `planfile.extensions` (5 functions, 1 classes)
📦 `planfile.importers` (2 functions)
📄 `planfile.importers.code2llm_importer` (9 functions, 1 classes)
📄 `planfile.importers.common` (2 functions)
📄 `planfile.importers.json_importer` (1 functions)
📄 `planfile.importers.redup_importer` (5 functions)
📄 `planfile.importers.vallm_importer` (10 functions, 1 classes)
📄 `planfile.importers.yaml_importer` (1 functions)
📦 `planfile.integrations`
📄 `planfile.integrations.base`
📄 `planfile.integrations.config` (14 functions, 1 classes)
📄 `planfile.integrations.generic`
📄 `planfile.integrations.github`
📄 `planfile.integrations.gitlab`
📄 `planfile.integrations.jira`
📦 `planfile.llm`
📄 `planfile.llm.adapters` (5 functions, 6 classes)
📄 `planfile.llm.client` (1 functions)
📄 `planfile.llm.generator` (6 functions)
📄 `planfile.llm.prompts` (1 functions)
📦 `planfile.loaders`
📄 `planfile.loaders.cli_loader` (10 functions)
📄 `planfile.loaders.yaml_loader` (15 functions)
📦 `planfile.mcp`
📄 `planfile.mcp.server` (4 functions)
📄 `planfile.models`
📄 `planfile.runner` (7 functions)
📄 `planfile.server_common` (1 functions)
📦 `planfile.sync`
📄 `planfile.sync.base` (21 functions, 4 classes)
📄 `planfile.sync.generic` (10 functions, 1 classes)
📄 `planfile.sync.github` (9 functions, 1 classes)
📄 `planfile.sync.gitlab` (8 functions, 1 classes)
📄 `planfile.sync.jira` (10 functions, 1 classes)
📦 `planfile.sync.markdown_backend`
📄 `planfile.sync.markdown_backend.backend` (2 functions, 1 classes)
📄 `planfile.sync.markdown_backend.constants`
📄 `planfile.sync.markdown_backend.files` (1 functions, 1 classes)
📄 `planfile.sync.markdown_backend.tickets` (6 functions, 1 classes)
📄 `planfile.sync.mock` (6 functions, 1 classes)
📄 `planfile.sync.operations` (15 functions)
📄 `planfile.sync.state` (5 functions, 1 classes)
📄 `planfile.sync.utils` (1 functions)
📦 `planfile.utils`
📄 `planfile.utils.metrics` (5 functions)
📄 `planfile.utils.priorities` (3 functions)
📄 `project`
📄 `run_examples` (13 functions)

## Requirements

- Python >= >=3.10
- typer >=0.12- rich >=13.0- pydantic >=2.0- pydantic-settings >=2.0- pyyaml >=6.0- requests >=2.31- httpx >=0.27- filelock >=3.0- python-dotenv >=1.0- PyGithub >=2.0

## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/semcod/planfile
cd planfile

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/semcod/planfile/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/semcod/planfile/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/semcod/planfile/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/semcod/planfile/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->

- [ci-cd-integration](information/ci-cd-integration.md)
