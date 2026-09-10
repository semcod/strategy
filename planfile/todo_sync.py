"""Synchronize markdown TODO checkboxes from planfile task status/results."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from planfile.strategy_input import load_strategy_mapping as _load_strategy

_DONE_STATUSES = {"success", "done", "completed", "already_fixed"}
_CHECKBOX_RE = re.compile(r"^(?P<prefix>\s*-\s*\[)(?P<state>[ xX])(?P<suffix>\]\s+)(?P<body>.*)$")


def _status_done(status: Any) -> bool:
    return str(status or "").strip().lower() in _DONE_STATUSES


def _get_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_marker(value: Any) -> str:
    return str(value or "").strip()


def _collect_markers_from_results(results: Iterable[Any] | None) -> set[str]:
    markers: set[str] = set()
    if not results:
        return markers

    for item in results:
        if not _status_done(_get_value(item, "status")):
            continue
        for key in ("ticket_id", "task_name", "name", "title", "id"):
            marker = _normalize_marker(_get_value(item, key))
            if marker:
                markers.add(marker)
    return markers


def _collect_markers_from_strategy(strategy: dict[str, Any]) -> set[str]:
    markers: set[str] = set()

    for task in strategy.get("tasks", []):
        if not isinstance(task, dict) or not _status_done(task.get("status")):
            continue
        for key in ("id", "title", "name"):
            marker = _normalize_marker(task.get(key))
            if marker:
                markers.add(marker)

    for sprint in strategy.get("sprints", []):
        if not isinstance(sprint, dict):
            continue
        for task in sprint.get("task_patterns", []):
            if not isinstance(task, dict) or not _status_done(task.get("status")):
                continue
            for key in ("id", "title", "name"):
                marker = _normalize_marker(task.get(key))
                if marker:
                    markers.add(marker)

    return markers


def _resolve_todo_config(
    strategy: dict[str, Any],
    strategy_path: Path,
    project_path: Path,
    enabled_override: bool | None,
) -> tuple[bool, Path]:
    markdown_cfg = (strategy.get("integrations") or {}).get("markdown") or {}

    if enabled_override is None:
        enabled = bool(markdown_cfg.get("sync_todo") or markdown_cfg.get("sync_on_plan_run"))
    else:
        enabled = bool(enabled_override)

    todo_file = markdown_cfg.get("todo_file", "TODO.md")
    todo_path = Path(todo_file)
    if not todo_path.is_absolute():
        strategy_dir = strategy_path.parent
        project_candidate = project_path / todo_path
        strategy_candidate = strategy_dir / todo_path
        todo_path = project_candidate if project_candidate.exists() else strategy_candidate

    return enabled, todo_path


def _line_matches_any_marker(body: str, markers: list[str]) -> bool:
    body_cf = body.casefold()
    return any(marker.casefold() in body_cf for marker in markers)


def sync_todo_checkboxes_from_planfile(
    strategy_path: str | Path,
    project_path: str | Path = ".",
    *,
    results: Iterable[Any] | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Sync TODO.md checkboxes from planfile status and execution results.

    Sync is controlled by planfile settings:

    integrations:
      markdown:
        sync_on_plan_run: true
        todo_file: TODO.md

    Args:
        strategy_path: Path to planfile YAML.
        project_path: Project root path.
        results: Optional task results from executor/CLI.
        enabled: Optional explicit enable/disable override.

    Returns:
        Report dict with keys: enabled, todo_path, updated.
    """
    project_root = Path(project_path).resolve()
    strategy_file = Path(strategy_path)
    if not strategy_file.is_absolute():
        strategy_file = (project_root / strategy_file).resolve()

    strategy = _load_strategy(strategy_file)
    enabled_flag, todo_path = _resolve_todo_config(strategy, strategy_file, project_root, enabled)

    report = {
        "enabled": enabled_flag,
        "todo_path": str(todo_path),
        "updated": 0,
    }

    if not enabled_flag or not todo_path.exists() or not todo_path.is_file():
        return report

    markers = _collect_markers_from_strategy(strategy)
    markers.update(_collect_markers_from_results(results))
    markers = {m for m in markers if len(m) >= 4}
    if not markers:
        return report

    marker_list = sorted(markers, key=len, reverse=True)

    try:
        lines = todo_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return report

    updated = 0
    out_lines: list[str] = []
    for line in lines:
        match = _CHECKBOX_RE.match(line)
        if not match:
            out_lines.append(line)
            continue

        if match.group("state").lower() != " ":
            out_lines.append(line)
            continue

        body = match.group("body")
        if _line_matches_any_marker(body, marker_list):
            out_lines.append(f"{match.group('prefix')}x{match.group('suffix')}{body}")
            updated += 1
        else:
            out_lines.append(line)

    if updated > 0:
        todo_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    report["updated"] = updated
    return report
