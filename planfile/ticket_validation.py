"""Validate planfile tickets against current project state.

This module provides a library-level API meant for cross-tool pre-flight checks
(e.g. llx, prefact adapters, CI runners). It does not mutate planfile files.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from planfile.strategy_input import load_strategy_mapping as _load_strategy


def _normalize_rule(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_rel_path(value: Any, project_root: Path) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    else:
        path = path.resolve()

    try:
        return str(path.relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _normalize_files(ticket: dict[str, Any], project_root: Path) -> list[str]:
    values: list[str] = []

    one = ticket.get("file")
    if one:
        values.append(str(one))

    many = ticket.get("files")
    if isinstance(many, list):
        values.extend(str(item) for item in many if item)

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        rel_path = _normalize_rel_path(value, project_root)
        if rel_path and rel_path not in seen:
            normalized.append(rel_path)
            seen.add(rel_path)
    return normalized


def _resolve_ticket_id(ticket: dict[str, Any], entry_ref: str) -> str:
    for key in ("id", "ticket_id"):
        value = str(ticket.get(key) or "").strip()
        if value:
            return value
    return entry_ref


def _iter_tasks_list(items: Any, base_ref: str) -> list[tuple[str, dict[str, Any]]]:
    output: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(items, list):
        return output
    for index, item in enumerate(items):
        if isinstance(item, dict):
            output.append((f"{base_ref}[{index}]", item))
    return output


def _iter_tickets_dict(items: Any, base_ref: str) -> list[tuple[str, dict[str, Any]]]:
    output: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(items, dict):
        return output
    for key, item in items.items():
        if isinstance(item, dict):
            output.append((f"{base_ref}.{key}", item))
    return output


def _collect_ticket_entries(strategy: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    entries: list[tuple[str, dict[str, Any]]] = []

    tasks = strategy.get("tasks")
    if isinstance(tasks, list):
        entries.extend(_iter_tasks_list(tasks, "tasks"))
    elif isinstance(tasks, dict):
        for category, patterns in tasks.items():
            entries.extend(_iter_tasks_list(patterns, f"tasks.{category}"))

    backlog = strategy.get("backlog")
    if isinstance(backlog, list):
        entries.extend(_iter_tasks_list(backlog, "backlog"))
    elif isinstance(backlog, dict):
        entries.extend(_iter_tickets_dict(backlog.get("tickets"), "backlog.tickets"))

    for sprint_idx, sprint in enumerate(strategy.get("sprints", [])):
        if not isinstance(sprint, dict):
            continue
        for field in ("task_patterns", "tasks"):
            entries.extend(_iter_tasks_list(sprint.get(field), f"sprints[{sprint_idx}].{field}"))
        entries.extend(_iter_tickets_dict(sprint.get("tickets"), f"sprints[{sprint_idx}].tickets"))

    return entries


def _parse_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_ticket_filters(ticket_ids: Iterable[Any] | None) -> set[str]:
    if ticket_ids is None:
        return set()
    normalized: set[str] = set()
    for ticket_id in ticket_ids:
        value = str(ticket_id or "").strip()
        if value:
            normalized.add(value)
    return normalized


def _build_issue_indexes(
    issue_records: Iterable[dict[str, Any]] | None,
    project_root: Path,
) -> tuple[set[tuple[str, str]], set[tuple[str, int]], bool]:
    if issue_records is None:
        return set(), set(), False

    rule_file_index: set[tuple[str, str]] = set()
    file_line_index: set[tuple[str, int]] = set()

    for issue in issue_records:
        if not isinstance(issue, dict):
            continue

        rule = _normalize_rule(issue.get("rule_id") or issue.get("rule"))
        line = _parse_positive_int(issue.get("line"))

        issue_files: list[str] = []
        if issue.get("file"):
            issue_files.append(str(issue["file"]))
        elif issue.get("path"):
            issue_files.append(str(issue["path"]))
        elif isinstance(issue.get("files"), list):
            issue_files.extend(str(item) for item in issue["files"] if item)

        for issue_file in issue_files:
            rel_path = _normalize_rel_path(issue_file, project_root)
            if not rel_path:
                continue
            if rule:
                rule_file_index.add((rule, rel_path))
            if line is not None:
                file_line_index.add((rel_path, line))

    return rule_file_index, file_line_index, True


def _count_file_lines(abs_path: Path) -> int | None:
    if not abs_path.exists() or not abs_path.is_file():
        return None
    try:
        with abs_path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def _validate_rule_anchor(
    record: dict[str, Any],
    rule_id: str,
    files: list[str],
    rule_file_index: set[tuple[str, str]],
    scan_available: bool,
) -> dict[str, Any]:
    if not scan_available:
        record["reason"] = "scan_unavailable"
        return record
    if any((rule_id, rel_path) in rule_file_index for rel_path in files):
        record["status"] = "current"
        record["reason"] = "rule_match_found"
    else:
        record["status"] = "stale"
        record["reason"] = "rule_no_longer_detected"
    return record


def _resolve_existing_files(files: list[str], project_root: Path) -> list[tuple[str, int]]:
    existing: list[tuple[str, int]] = []
    for rel_path in files:
        abs_path = (project_root / rel_path).resolve()
        total_lines = _count_file_lines(abs_path)
        if total_lines is not None:
            existing.append((rel_path, total_lines))
    return existing


def _validate_line_anchor(
    record: dict[str, Any],
    files: list[str],
    line: int,
    project_root: Path,
    file_line_index: set[tuple[str, int]],
    scan_available: bool,
) -> dict[str, Any]:
    existing_files = _resolve_existing_files(files, project_root)

    if not existing_files:
        record["status"] = "stale"
        record["reason"] = "files_missing"
        return record

    if all(line > total_lines for _, total_lines in existing_files):
        record["status"] = "stale"
        record["reason"] = "line_out_of_range"
        return record

    if scan_available and any((rel_path, line) in file_line_index for rel_path, _ in existing_files):
        record["status"] = "current"
        record["reason"] = "line_match_found"
        return record

    record["reason"] = "line_exists_but_not_confirmed"
    return record


def _validate_file_only(
    record: dict[str, Any],
    files: list[str],
    project_root: Path,
) -> dict[str, Any]:
    if any((project_root / rel_path).exists() for rel_path in files):
        record["reason"] = "file_exists_but_no_rule_or_line"
    else:
        record["status"] = "stale"
        record["reason"] = "files_missing"
    return record


def _validate_ticket(
    ticket: dict[str, Any],
    entry_ref: str,
    project_root: Path,
    rule_file_index: set[tuple[str, str]],
    file_line_index: set[tuple[str, int]],
    scan_available: bool,
) -> dict[str, Any]:
    ticket_id = _resolve_ticket_id(ticket, entry_ref)
    name = str(ticket.get("title") or ticket.get("name") or "").strip()
    rule_id = _normalize_rule(ticket.get("rule_id"))
    files = _normalize_files(ticket, project_root)
    line = _parse_positive_int(ticket.get("line"))

    record: dict[str, Any] = {
        "ticket_id": ticket_id,
        "entry_ref": entry_ref,
        "name": name,
        "rule_id": rule_id,
        "files": files,
        "line": line,
        "status": "unknown",
        "reason": "insufficient_data",
    }

    if rule_id and files:
        return _validate_rule_anchor(record, rule_id, files, rule_file_index, scan_available)

    if files and line is not None:
        return _validate_line_anchor(record, files, line, project_root, file_line_index, scan_available)

    if files:
        return _validate_file_only(record, files, project_root)

    return record


def validate_planfile_tickets(
    strategy_path: str | Path,
    project_path: str | Path = ".",
    *,
    issue_records: Iterable[dict[str, Any]] | None = None,
    ticket_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Validate ticket freshness and return a structured report.

    Args:
        strategy_path: Path to a planfile/strategy YAML.
        project_path: Project root for file normalization.
        issue_records: Optional iterable of issue dicts from an external scanner
            (e.g. prefact). Supported keys: ``rule_id`` or ``rule``, ``file`` or
            ``path``, and optional ``line``.
        ticket_ids: Optional ticket IDs to validate. When provided, only matching
            ticket entries are included in the report.

    Returns:
        Report dictionary with per-ticket statuses and aggregate counters.
        Status values:
        - ``current``: ticket still confirmed by scan/file anchors
        - ``stale``: ticket clearly obsolete (missing file/rule/line)
        - ``unknown``: insufficient confidence; needs manual or LLM review
    """
    project_root = Path(project_path).resolve()
    strategy_file = Path(strategy_path)
    if not strategy_file.is_absolute():
        strategy_file = (project_root / strategy_file).resolve()

    strategy = _load_strategy(strategy_file)
    entries = _collect_ticket_entries(strategy)
    requested_ticket_ids = _normalize_ticket_filters(ticket_ids)
    rule_file_index, file_line_index, scan_available = _build_issue_indexes(issue_records, project_root)

    tickets_report: list[dict[str, Any]] = []
    for entry_ref, ticket in entries:
        record = _validate_ticket(
            ticket=ticket,
            entry_ref=entry_ref,
            project_root=project_root,
            rule_file_index=rule_file_index,
            file_line_index=file_line_index,
            scan_available=scan_available,
        )
        if requested_ticket_ids and record["ticket_id"] not in requested_ticket_ids:
            continue
        tickets_report.append(record)

    confirmed_current_ids = [item["ticket_id"] for item in tickets_report if item["status"] == "current"]
    stale_ids = [item["ticket_id"] for item in tickets_report if item["status"] == "stale"]
    unknown_ids = [item["ticket_id"] for item in tickets_report if item["status"] == "unknown"]

    return {
        "strategy_path": str(strategy_file),
        "project_path": str(project_root),
        "scan_available": scan_available,
        "filtered_ticket_ids": sorted(requested_ticket_ids),
        "total": len(tickets_report),
        "current": len(confirmed_current_ids),
        "stale": len(stale_ids),
        "unknown": len(unknown_ids),
        "confirmed_current_ticket_ids": confirmed_current_ids,
        "stale_ticket_ids": stale_ids,
        "review_needed_ticket_ids": unknown_ids,
        "tickets": tickets_report,
    }
