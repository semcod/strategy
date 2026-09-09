"""Standalone strategy executor that works without LLX dependencies."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from planfile.core.models import Strategy, Task


logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of executing a task."""
    task_name: str
    status: str  # "success", "failed", "skipped", "dry_run"
    model_used: str
    response: str = ""
    error: str | None = None
    execution_time: float | None = None


class LLMClient:
    """Simple LLM client interface."""

    def __init__(self, client_func: Callable, config: dict[str, Any] = None):
        """Initialize with a client function.
        
        Args:
            client_func: Function that takes (messages, model) and returns response
            config: Configuration dictionary
        """
        self.client_func = client_func
        self.config = config or {}

    def chat(self, messages: list[dict[str, str]], model: str) -> str:
        """Send chat messages and return response."""
        return self.client_func(messages, model)


class StrategyExecutor:
    """Standalone strategy executor."""

    def __init__(self, client: LLMClient | None = None, config: dict[str, Any] | None = None):
        """Initialize executor.
        
        Args:
            client: LLM client instance (optional)
            config: Configuration dictionary with model mappings
        """
        self.client = client
        self.config = config or self._default_config()

    def _default_config(self) -> dict[str, Any]:
        """Default configuration."""
        return {
            'model_map': {
                'local': 'ollama/qwen2.5-coder:7b',
                'cheap': 'openrouter/meta-llama/llama-3.2-3b-instruct:free',
                'balanced': 'openai/gpt-5.4-mini',
                'premium': 'x-ai/grok-code-fast-1',
                'free': 'openrouter/meta-llama/llama-3.2-3b-instruct:free'
            },
            'api_keys': {
                'openai': None,
                'openrouter': None,
                'anthropic': None
            }
        }

    def execute_strategy(
        self,
        strategy: Strategy | str | Path | dict,
        project_path: str | Path = ".",
        *,
        dry_run: bool = False,
        sprint_filter: int | None = None,
        model_override: str | None = None,
        on_progress: Callable[[str], None] | None = None
    ) -> list[TaskResult]:
        """Execute a strategy.
        
        Args:
            strategy: Strategy object or path to YAML file
            project_path: Path to the project
            dry_run: If True, only simulate execution
            sprint_filter: Execute only this sprint (optional)
            model_override: Override model selection
            on_progress: Progress callback function
            
        Returns:
            List of task results
        """
        # Load strategy if needed
        if not isinstance(strategy, Strategy):
            strategy = Strategy.load_flexible(strategy)

        results = []

        # Process sprints
        for sprint in strategy.sprints:
            if sprint_filter and sprint.id != sprint_filter:
                continue

            if on_progress:
                on_progress(f"Sprint {sprint.id}: {sprint.name}")

            # Process tasks
            for task in sprint.tasks:
                if on_progress:
                    on_progress(f"  Task: {task.name}")

                result = self._execute_task(
                    task,
                    project_path,
                    dry_run,
                    model_override
                )
                results.append(result)

        return results

    def _execute_task(
        self,
        task: Task,
        project_path: str | Path,
        dry_run: bool,
        model_override: str | None = None
    ) -> TaskResult:
        """Execute a single task."""
        start_time = time.time()

        try:
            # Select model
            model = model_override or self._select_model(task)

            if dry_run:
                return TaskResult(
                    task_name=task.name,
                    status="dry_run",
                    model_used=model,
                    execution_time=time.time() - start_time
                )

            # Build prompt
            prompt = self._build_prompt(task, project_path)

            # Execute if client available
            if self.client:
                response = self.client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model
                )
                content = response if isinstance(response, str) else str(response)
            else:
                # Mock execution for testing
                content = f"Mock execution of task '{task.name}' with model {model}\n\n" \
                         f"Task type: {task.type}\n" \
                         f"Description: {task.description}\n\n" \
                         f"This is a simulated response. Configure a client to get actual LLM responses."

            return TaskResult(
                task_name=task.name,
                status="success",
                model_used=model,
                response=content,
                execution_time=time.time() - start_time
            )

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return TaskResult(
                task_name=task.name,
                status="failed",
                model_used=model or "unknown",
                error=str(e),
                execution_time=time.time() - start_time
            )

    def _select_model(self, task: Task) -> str:
        """Select model based on task hints and type."""
        # Get model hint from task
        hints = task.model_hints or {}
        hint = hints.get('implementation') or hints.get('design', 'balanced')

        # Normalize hint
        if hint == 'free':
            hint = 'cheap'

        # Get model map
        model_map = self.config.get('model_map', {})

        # Select model based on task type if no hint
        if not hints:
            if task.type in ['chore', 'documentation']:
                hint = 'cheap'
            elif task.type in ['tech_debt', 'refactor']:
                hint = 'balanced'
            else:
                hint = 'balanced'

        return model_map.get(hint, model_map.get('balanced', 'openai/gpt-5.4-mini'))

    def _build_prompt(self, task: Task, project_path: str | Path) -> str:
        """Build execution prompt for task."""
        # Try to get project metrics if available
        metrics = self._get_project_metrics(project_path)

        prompt = f"""## Task: {task.name}

Type: {task.type}
Priority: {task.priority}

Description:
{task.description}

"""

        if metrics:
            prompt += f"""
## Project Context
    - Files: {metrics.get('total_files', 'N/A')}
    - Lines of code: {metrics.get('total_lines', 'N/A')}
    - Average complexity: {metrics.get('avg_cc', 'N/A')}
    - Max complexity: {metrics.get('max_cc', 'N/A')}
    - File-read coverage complete: {metrics.get('complete', 'unknown')}
    - Files omitted due to read errors: {metrics.get('files_failed', 'unknown')}

"""

        prompt += """
## Instructions
Please execute this task. Provide:
1. Specific actions to take
    2. Code changes if applicable (with file paths)
3. Any additional context or notes

Focus on practical, actionable steps.
"""

        return prompt

    def _get_project_metrics(self, project_path: str | Path) -> dict | None:
        """Get project metrics if available."""
        try:
            path = Path(project_path)
            py_files = list(path.rglob("*.py"))

            # Simple metrics calculation
            total_lines = 0
            max_cc = 0
            total_files = len(py_files)
            files_failed = 0

            for py_file in py_files:
                if py_file.is_file():
                    try:
                        content = py_file.read_text(encoding='utf-8')
                        lines = len(content.splitlines())
                        total_lines += lines

                        # Simple CC estimation (count control flow keywords)
                        cc = content.count(' if ') + content.count(' for ') + content.count(' while ') + content.count(' except ')
                        max_cc = max(max_cc, cc)
                    except (OSError, UnicodeDecodeError) as exc:
                        files_failed += 1
                        logger.warning(
                            "PLANFILE_METRICS_FILE_READ_FAILED error_type=%s",
                            type(exc).__name__,
                        )

            avg_cc = max_cc / total_files if total_files > 0 else 0

            return {
                'total_files': total_files,
                'total_lines': total_lines,
                'avg_cc': round(avg_cc, 1),
                'max_cc': max_cc,
                'files_failed': files_failed,
                'complete': files_failed == 0,
            }
        except OSError as exc:
            logger.warning(
                "PLANFILE_METRICS_UNAVAILABLE error_type=%s", type(exc).__name__
            )
            return None


# Convenience functions for different LLM providers

def create_openai_client(api_key: str, model: str = "gpt-5.4-mini") -> LLMClient:
    """Create an OpenAI client."""
    try:
        import openai

        def client_func(messages, model):
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            return response.choices[0].message.content

        return LLMClient(client_func)
    except ImportError:
        raise ImportError("OpenAI library not installed. Install with: pip install openai")


def create_litellm_client(api_key: str = None, model: str = "gpt-5.4-mini") -> LLMClient:
    """Create a LiteLLM client."""
    try:
        import litellm

        def client_func(messages, model):
            response = litellm.completion(
                model=model,
                messages=messages,
                api_key=api_key
            )
            return response.choices[0].message.content

        return LLMClient(client_func)
    except ImportError:
        raise ImportError("LiteLLM library not installed. Install with: pip install litellm")


# Convenience function for backward compatibility
def execute_strategy(
    strategy_path: str | Path,
    project_path: str | Path = ".",
    *,
    dry_run: bool = False,
    sprint_filter: int | None = None,
    client: LLMClient | None = None,
    **kwargs
) -> list[TaskResult]:
    """Execute strategy from file - convenience function."""
    executor = StrategyExecutor(client=client)
    return executor.execute_strategy(
        strategy=strategy_path,
        project_path=project_path,
        dry_run=dry_run,
        sprint_filter=sprint_filter,
        **kwargs
    )
