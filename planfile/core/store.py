from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import timezone, datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import RLock

import yaml
from pydantic import BaseModel

from .models import TICKET_CONTRACT_VERSION, Ticket
from .store_files import StoreFileMixin
from .store_tickets import TicketStoreMixin


class ImmutableTerminalReopenError(RuntimeError):
    """Raised when an ordinary mutation tries to reactivate done/canceled work."""


class TicketIndexContentionError(RuntimeError):
    """Raised when the disposable index cannot capture a stable snapshot."""


class TicketUpdatedAtConflictError(RuntimeError):
    """Raised when a ticket changed after the caller observed it."""


class Store(StoreFileMixin, TicketStoreMixin):
    """File-based ticket store using .planfile/ directory."""

    DEFAULT_ARCHIVE_CONFIG = {
        "enabled": True,
        "max_current_tickets": 100,
        "max_current_bytes": 1_000_000,
        "retain_terminal_tickets": 20,
        "retain_terminal_days": 0,
        "terminal_statuses": ["done", "canceled", "failed", "blocked"],
    }
    DEFAULT_STORAGE_CONFIG = {
        "backend": "single-yaml",
        "shard_size": 100,
        "custom_shards": 16,
        "index": "none",
    }
    SPRINT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    IMMUTABLE_TERMINAL_STATUSES = {"done", "canceled"}
    TERMINAL_STATUSES = {"done", "canceled", "failed", "blocked"}

    def __init__(self, directory: str | Path):
        self.project_dir = Path(directory).resolve()
        self.base_dir = self.project_dir / ".planfile"
        self._config_path = self.base_dir / "config.yaml"
        self._sprints_dir = self.base_dir / "sprints"
        self._lock_path = self.base_dir / ".store.lock"
        self._operations_path = self.base_dir / "events" / "operations.jsonl"
        self._forensic_log_path = self.base_dir / "events" / "logs.dsl.txt"
        self._forensic_log_history_dir = self.base_dir / "events" / "history"
        self._forensic_log_date_path = self.base_dir / "events" / ".logs.dsl.date"
        self._forensic_log_receipt_path = self.base_dir / "events" / ".logs.dsl.v1"
        self._evidence_dir = self.base_dir / "evidence"
        self._ticket_index_path = self.base_dir / "index" / "tickets.sqlite3"
        self._ticket_index_rebuild_lock_path = self.base_dir / "index" / ".rebuild.lock"
        self._ticket_index_rebuild_deferred_until = 0.0
        self._ticket_index_signature_cache: tuple[float, tuple, tuple] | None = None
        self._ticket_index_signature_cache_lock = RLock()
        self._history_locations_path = self.base_dir / "index" / "history-locations.yaml"

    def _storage_config(self) -> dict:
        configured = self._read_config().get("storage") or {}
        if not isinstance(configured, dict):
            configured = {}
        result = dict(self.DEFAULT_STORAGE_CONFIG)
        result.update(configured)
        if result.get("backend") not in {"single-yaml", "sharded-yaml"}:
            result["backend"] = "single-yaml"
        if result.get("index") not in {"none", "sqlite"}:
            result["index"] = "none"
        for key in ("shard_size", "custom_shards"):
            try:
                result[key] = max(1, int(result[key]))
            except (TypeError, ValueError):
                result[key] = self.DEFAULT_STORAGE_CONFIG[key]
        result["custom_shards"] = min(result["custom_shards"], 256)
        return result

    def storage_backend(self) -> str:
        """Return the configured physical ticket backend."""
        return str(self._storage_config()["backend"])

    def _uses_sharded_storage(self) -> bool:
        return self.storage_backend() == "sharded-yaml"

    def _sharded_storage(self):
        from planfile.core.sharded_yaml import ShardedYamlStorage

        config = self._storage_config()
        return ShardedYamlStorage(
            self._sprints_dir,
            self._write_yaml_atomic,
            shard_size=config["shard_size"],
            custom_shards=config["custom_shards"],
        )

    def _append_operational_line(self, line: str) -> None:
        """Append one verified SODL event while the caller holds mutation_lock."""
        self._append_operational_lines([line])

    def _append_operational_lines(self, lines: list[str]) -> None:
        """Append verified SODL events with one durable journal flush."""
        from planfile.core.operational_dsl import parse

        rows = []
        events = []
        for line in lines:
            event = parse(line)
            events.append(event)
            rows.append(
                json.dumps(
                    {"schema": event["schema"], "event": event, "dsl": line},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        if not rows:
            return
        self._ensure_forensic_log_projection_unlocked()
        self._append_forensic_events_unlocked(events)
        self._operations_path.parent.mkdir(parents=True, exist_ok=True)
        with self._operations_path.open("a", encoding="utf-8") as handle:
            handle.write("".join(f"{row}\n" for row in rows))
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _forensic_event_date(event: dict) -> str:
        value = str(event.get("timestamp") or "")[:10]
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return datetime.now(timezone.utc).date().isoformat()

    def _forensic_path_for_date(self, value: str) -> Path:
        today = datetime.now(timezone.utc).date().isoformat()
        if value == today:
            return self._forensic_log_path
        return self._forensic_log_history_dir / f"logs-{value}.dsl.txt"

    def _rotate_forensic_log_unlocked(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        try:
            recorded_date = self._forensic_log_date_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            recorded_date = ""
        if recorded_date and recorded_date != today and self._forensic_log_path.exists():
            destination = self._forensic_log_history_dir / f"logs-{recorded_date}.dsl.txt"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a", encoding="utf-8") as output:
                with self._forensic_log_path.open("r", encoding="utf-8") as source:
                    shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            self._forensic_log_path.unlink()
        self._forensic_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._forensic_log_path.touch(exist_ok=True)
        from planfile.core.fastio import _atomic_write_text

        _atomic_write_text(self._forensic_log_date_path, f"{today}\n")

    def _append_forensic_events_unlocked(self, events: list[dict]) -> None:
        from planfile.core.forensic_log_dsl import serialize as forensic_line

        self._rotate_forensic_log_unlocked()
        grouped: dict[Path, list[str]] = {}
        for event in events:
            path = self._forensic_path_for_date(self._forensic_event_date(event))
            grouped.setdefault(path, []).append(forensic_line(event))
        for path, projected in grouped.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write("".join(f"{line}\n" for line in projected))
                handle.flush()
                os.fsync(handle.fileno())

    def _ensure_forensic_log_projection_unlocked(self) -> None:
        if self._forensic_log_receipt_path.exists():
            self._rotate_forensic_log_unlocked()
            return
        self._rotate_forensic_log_unlocked()
        if self._operations_path.exists():
            batch = []
            with self._operations_path.open("r", encoding="utf-8") as source:
                for raw in source:
                    if not raw.strip():
                        continue
                    try:
                        row = json.loads(raw)
                    except ValueError:
                        continue
                    event = row.get("event") if isinstance(row, dict) else None
                    if isinstance(event, dict):
                        batch.append(event)
                    if len(batch) >= 250:
                        self._append_forensic_events_unlocked(batch)
                        batch.clear()
            if batch:
                self._append_forensic_events_unlocked(batch)
        from planfile.core.fastio import _atomic_write_text

        _atomic_write_text(
            self._forensic_log_receipt_path,
            "schema=planfile.forensic-log-projection/v1\n",
        )

    def ensure_forensic_log_projection(self) -> None:
        """Backfill the compact public log once, then keep it append-only."""
        if self._forensic_log_receipt_path.exists():
            try:
                recorded_date = self._forensic_log_date_path.read_text(
                    encoding="utf-8"
                ).strip()
            except FileNotFoundError:
                recorded_date = ""
            if recorded_date == datetime.now(timezone.utc).date().isoformat():
                return
        with self.mutation_lock():
            self._ensure_forensic_log_projection_unlocked()

    def forensic_log_lines(
        self,
        *,
        date: str | None = None,
        ticket_id: str | None = None,
        event_type: str | None = None,
        limit: int = 500,
    ) -> list[str]:
        """Return a bounded oldest-to-newest slice of the readable log."""
        from collections import deque

        from planfile.core.forensic_log_dsl import parse

        self.ensure_forensic_log_projection()
        selected_date = date or datetime.now(timezone.utc).date().isoformat()
        path = self._forensic_path_for_date(selected_date)
        result: deque[str] = deque(maxlen=max(1, min(int(limit), 5000)))
        try:
            source = path.open("r", encoding="utf-8")
        except FileNotFoundError:
            return []
        with source:
            for raw in source:
                line = raw.rstrip("\r\n")
                if not line:
                    continue
                if ticket_id or event_type:
                    try:
                        record = parse(line)
                    except ValueError:
                        continue
                    if ticket_id and record["ticket_id"] != ticket_id:
                        continue
                    if event_type and record["type"] != event_type:
                        continue
                result.append(line)
        return list(result)

    def forensic_log_days(self) -> list[dict]:
        """Describe every public daily PLOG partition, newest first."""
        self.ensure_forensic_log_projection()
        today = datetime.now(timezone.utc).date().isoformat()
        paths = [(today, self._forensic_log_path)]
        for path in self._forensic_log_history_dir.glob("logs-*.dsl.txt"):
            paths.append((path.name.removeprefix("logs-").removesuffix(".dsl.txt"), path))
        result = []
        for value, path in sorted(paths, reverse=True):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            result.append({"date": value, "bytes": stat.st_size, "file": path.name})
        return result

    def append_management_event(self, event: dict) -> None:
        """Persist a compact management observation in the same audit stream."""
        from planfile.core.operational_dsl import line as operational_line

        ticket_id = str(event.get("ticket_id") or "-")
        action = str(event.get("action") or event.get("type") or "observe")
        source = str(event.get("source") or event.get("tool") or "planfile.api")
        actor = str(event.get("actor") or event.get("tool") or source)
        ticket = event.get("ticket") if isinstance(event.get("ticket"), dict) else {}
        execution = ticket.get("execution") if isinstance(ticket.get("execution"), dict) else {}
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        message = str(
            event.get("message")
            or execution.get("last_error")
            or details.get("error")
            or ""
        )
        traced_logic = {
            key: event.get(key, details.get(key))
            for key in (
                "decision",
                "outcome",
                "error",
                "idempotency_key",
            )
            if event.get(key, details.get(key)) not in (None, "", [], {})
        }
        data = {
            "payload": {
                "action": action,
                "name": str(ticket.get("name") or ""),
                "message": message,
                "level": str(event.get("level") or "info"),
                "queue": str(event.get("queue") or execution.get("queue") or "default"),
                "reason": str(event.get("reason") or message),
                "status": str(ticket.get("status") or event.get("status") or "recorded"),
                "execution_state": str(execution.get("state") or ""),
                **traced_logic,
            }
        }
        with self.mutation_lock():
            self._append_operational_line(
                operational_line(
                    timestamp=event.get("created_at"),
                    kind="management",
                    source=source,
                    ticket_id=ticket_id,
                    actor=actor,
                    oql=f"event.{action}",
                    uri=f"planfile://events/{action}/observe",
                    mode="observe",
                    status=str(ticket.get("status") or event.get("status") or "recorded"),
                    correlation_id=str(event.get("correlation_id") or ticket_id),
                    causation_id=str(event.get("causation_id") or "-"),
                    receipt_ref=str(event.get("receipt_ref") or "-"),
                    replayable=False,
                    data=data,
                )
            )

    def _ticket_evidence_path(self, ticket_id: str) -> Path:
        value = str(ticket_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise ValueError("evidence_ticket_id_invalid")
        return self._evidence_dir / f"{value}.jsonl"

    def _ticket_evidence_events(self, ticket_id: str) -> list[dict]:
        path = self._ticket_evidence_path(ticket_id)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        events = []
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (TypeError, ValueError):
                logger = __import__("logging").getLogger("planfile.store")
                logger.warning("skipping invalid evidence event for %s", ticket_id)
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    @staticmethod
    def _evidence_item_key(item) -> str:
        if not isinstance(item, dict):
            return ""
        return str(
            item.get("idempotency_key")
            or item.get("evidence_id")
            or item.get("execution_id")
            or ""
        )

    def _apply_ticket_evidence_events(self, ticket_data: dict, events: list[dict]) -> dict:
        projected = dict(ticket_data)
        outputs = dict(projected.get("outputs") or {})
        result = dict(outputs.get("result") or {})
        notes = list(outputs.get("notes") or [])
        artifacts = list(outputs.get("artifacts") or [])
        latest = str(projected.get("updated_at") or "")
        for event in events:
            collection = str(event.get("collection") or "")
            evidence = event.get("evidence")
            if not collection or not isinstance(evidence, dict):
                continue
            values = list(result.get(collection) or [])
            key = str(event.get("idempotency_key") or self._evidence_item_key(evidence))
            if key and any(self._evidence_item_key(item) == key for item in values):
                pass
            else:
                values.append(evidence)
                result[collection] = values
            notes = list(dict.fromkeys([*notes, *(str(item) for item in event.get("notes") or [] if str(item))]))
            artifacts = list(dict.fromkeys([*artifacts, *(str(item) for item in event.get("artifacts") or [] if str(item))]))
            latest = max(latest, str(event.get("timestamp") or ""))
        if events:
            outputs["result"] = result
            outputs["notes"] = notes
            outputs["artifacts"] = artifacts
            projected["outputs"] = outputs
            if latest:
                projected["updated_at"] = latest
        return projected

    def _project_ticket_evidence(self, ticket_data: dict) -> dict:
        ticket_id = str(ticket_data.get("id") or "")
        return self._apply_ticket_evidence_events(
            ticket_data,
            self._ticket_evidence_events(ticket_id),
        )

    def _evidence_revision(self) -> tuple:
        try:
            paths = sorted(self._evidence_dir.glob("*.jsonl"))
        except OSError:
            return ()
        revision = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            revision.append((path.name, stat.st_mtime_ns, stat.st_size))
        return tuple(revision)

    def _ticket_evidence_revision(self, ticket_ids) -> tuple:
        """Return evidence revisions only for tickets in one sprint.

        A receipt appended to one active ticket must not invalidate validated
        ticket models for every archived sprint. The global revision remains
        the correct signature for cross-sprint API response caches, while this
        scoped variant keeps model-cache invalidation proportional to the
        sprint that actually changed.
        """
        revision = []
        for ticket_id in ticket_ids:
            try:
                path = self._ticket_evidence_path(str(ticket_id))
                stat = path.stat()
            except (FileNotFoundError, ValueError):
                continue
            revision.append((path.name, stat.st_mtime_ns, stat.st_size))
        return tuple(revision)

    def _append_ticket_evidence_event(self, ticket_id: str, event: dict) -> None:
        path = self._ticket_evidence_path(ticket_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{row}\n")
            handle.flush()
            os.fsync(handle.fileno())

    def operational_events(self, *, limit: int = 200, ticket_id: str | None = None) -> list[dict]:
        """Read the append-only operational journal, newest first."""
        from collections import deque

        bounded: deque[dict] = deque(maxlen=max(1, min(int(limit), 5000)))
        try:
            source = self._operations_path.open("r", encoding="utf-8")
        except FileNotFoundError:
            return []
        with source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if ticket_id and str((row.get("event") or {}).get("ticket_id") or "") != str(ticket_id):
                    continue
                bounded.append(row)
        return list(reversed(bounded))

    @contextmanager
    def mutation_lock(self):
        """Serialize multi-process YAML mutations."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_path.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            self._invalidate_ticket_index_signature_cache()
            yield
        finally:
            self._invalidate_ticket_index_signature_cache()
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            lock_file.close()

    def _write_yaml_atomic(self, path: Path, data: dict, *, allow_unicode: bool = False) -> None:
        from planfile.core.fastio import dump_yaml, write_mirror

        path.parent.mkdir(parents=True, exist_ok=True)
        content = dump_yaml(data, allow_unicode=allow_unicode)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            # Stat immediately after our own replace, under mutation_lock() (no other
            # writer can be interleaved here) — pass it through instead of letting
            # write_mirror() re-stat independently later (see its docstring).
            mtime_ns = path.stat().st_mtime_ns
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        write_mirror(path, data, mtime_ns=mtime_ns)

    def is_initialized(self) -> bool:
        return self._config_path.exists()

    def load_sprint(self, sprint: str) -> dict:
        """Load sprint data from YAML."""
        if self._uses_sharded_storage():
            data = self._sharded_storage().load_sprint(sprint)
            return data.get("sprint") or data
        path = self._sprint_file(sprint)
        data = self._read_yaml_cached(path) or {}
        return data.get("sprint") or data

    def load_backlog(self) -> dict:
        """Load backlog data from YAML."""
        if self._uses_sharded_storage():
            data = self._sharded_storage().load_sprint("backlog")
            return data.get("sprint") or data
        path = self._sprint_file("backlog")
        data = self._read_yaml_cached(path) or {}
        return data.get("sprint") or data

    def save_sprint(self, sprint: str, data: dict) -> None:
        """Merge sprint data back to YAML without dropping concurrent mutations.

        Callers such as external-system sync intentionally hold an in-memory
        snapshot while doing network work.  Replacing the whole sprint with
        that snapshot can erase tickets created after ``load_sprint()``.  The
        mutation lock serializes writers, but it cannot make a stale snapshot
        current, so merge it with a fresh read taken inside the lock.

        Tickets absent from ``data`` are preserved.  Explicit deletion must go
        through ``delete_ticket(s)``.  When the same ticket changed on both
        sides, the record with the newer ``updated_at`` wins; a stale bulk
        save therefore fails closed instead of reverting a newer lifecycle
        transition.
        """
        self._sprint_file(sprint)  # validate before acquiring the mutation lock
        if self._uses_sharded_storage():
            with self.mutation_lock():
                storage = self._sharded_storage()
                current = storage.load_sprint(sprint)
                incoming = self._exclude_tickets_owned_by_history(sprint, data)
                merged = self._merge_sprint_snapshots(current, incoming)
                storage.write_sprint(sprint, merged)
                self._invalidate_sharded_cache(sprint)
            if sprint == "current":
                self.archive_completed()
            return

        path = self._sprint_file(sprint)
        with self.mutation_lock():
            from planfile.core.fastio import read_yaml_fast

            current = read_yaml_fast(path) or {}
            incoming = self._exclude_tickets_owned_by_history(sprint, data)
            merged = self._merge_sprint_snapshots(current, incoming)
            self._write_yaml_atomic(path, merged, allow_unicode=True)
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(path), None)
        if sprint == "current":
            self.archive_completed()

    @staticmethod
    def _ticket_timestamp(ticket: dict) -> datetime:
        for key in ("updated_at", "created_at"):
            value = ticket.get(key) if isinstance(ticket, dict) else None
            if isinstance(value, datetime):
                parsed = value
            elif isinstance(value, str) and value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)

    @classmethod
    def _merge_sprint_snapshots(cls, current: dict, incoming: dict) -> dict:
        """Return a wrapped sprint snapshot that preserves newer disk state."""
        current_root = current.get("sprint", current) if isinstance(current, dict) else {}
        incoming_root = incoming.get("sprint", incoming) if isinstance(incoming, dict) else {}
        current_root = current_root if isinstance(current_root, dict) else {}
        incoming_root = incoming_root if isinstance(incoming_root, dict) else {}

        merged_root = {**current_root, **incoming_root}
        current_tickets = current_root.get("tickets") or {}
        incoming_tickets = incoming_root.get("tickets") or {}
        current_tickets = current_tickets if isinstance(current_tickets, dict) else {}
        incoming_tickets = incoming_tickets if isinstance(incoming_tickets, dict) else {}

        merged_tickets = dict(current_tickets)
        for ticket_id, incoming_ticket in incoming_tickets.items():
            current_ticket = current_tickets.get(ticket_id)
            if (
                isinstance(current_ticket, dict)
                and isinstance(incoming_ticket, dict)
                and cls._ticket_timestamp(current_ticket) > cls._ticket_timestamp(incoming_ticket)
            ):
                continue
            merged_tickets[ticket_id] = incoming_ticket
        merged_root["tickets"] = merged_tickets
        return {"sprint": merged_root}

    def save_backlog(self, data: dict) -> None:
        """Merge backlog data with the same concurrency guarantees as a sprint."""
        self.save_sprint("backlog", data)

    def init(self) -> None:
        """Create the .planfile/ structure from scratch."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sprints_dir.mkdir(exist_ok=True)
        if not self._config_path.exists():
            self._config_path.write_text(
                yaml.dump(
                    {
                        "project": self.project_dir.name,
                        "prefix": "PLF",
                        "next_id": 1,
                        "archive": dict(self.DEFAULT_ARCHIVE_CONFIG),
                        "storage": dict(self.DEFAULT_STORAGE_CONFIG),
                    }
                ),
                encoding="utf-8",
            )
        if self._uses_sharded_storage():
            storage = self._sharded_storage()
            storage.ensure_sprint(
                "current",
                {"id": "sprint-001", "name": "Sprint 1", "status": "active"},
            )
            storage.ensure_sprint(
                "backlog",
                {"id": "backlog", "name": "Backlog", "status": "active"},
            )
            return
        current = self._sprints_dir / "current.yaml"
        if not current.exists():
            current.write_text(
                yaml.dump(
                    {
                        "sprint": {
                            "id": "sprint-001",
                            "name": "Sprint 1",
                            "status": "active",
                            "tickets": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
        backlog = self._sprints_dir / "backlog.yaml"
        if not backlog.exists():
            backlog.write_text(
                yaml.dump(
                    {
                        "sprint": {
                            "id": "backlog",
                            "name": "Backlog",
                            "status": "active",
                            "tickets": {},
                        }
                    }
                ),
                encoding="utf-8",
            )

    def _read_config(self) -> dict:
        if not self._config_path.exists():
            return {"project": "unknown", "prefix": "PLF", "next_id": 1}
        return yaml.safe_load(self._config_path.read_text()) or {}

    def _write_config(self, config: dict) -> None:
        self._write_yaml_atomic(self._config_path, config)

    def _history_locations(self) -> dict[str, str]:
        """Return the small durable ticket-to-history locator projection."""
        if not self._history_locations_path.exists():
            return {}
        data = self._read_yaml_cached(self._history_locations_path) or {}
        locations = data.get("tickets", {}) if isinstance(data, dict) else {}
        if not isinstance(locations, dict):
            return {}
        return {
            str(ticket_id): str(sprint)
            for ticket_id, sprint in locations.items()
            if self.SPRINT_ID_PATTERN.fullmatch(str(sprint))
        }

    def _record_history_locations_unlocked(self, locations: dict[str, str]) -> None:
        if not locations:
            return
        current = self._history_locations()
        current.update(locations)
        self._write_yaml_atomic(
            self._history_locations_path,
            {
                "schema": "planfile.history-locations/v1",
                "tickets": current,
            },
            allow_unicode=True,
        )

    def _exclude_tickets_owned_by_history(self, sprint: str, data: dict) -> dict:
        """Prevent a stale bulk snapshot from resurrecting archived tickets."""
        if sprint.startswith(("history-", "archive-")):
            return data
        locations = self._history_locations()
        if not locations or not isinstance(data, dict):
            return data
        root = data.get("sprint", data)
        if not isinstance(root, dict) or not isinstance(root.get("tickets"), dict):
            return data
        filtered = {
            ticket_id: ticket
            for ticket_id, ticket in root["tickets"].items()
            if locations.get(str(ticket_id)) in {None, sprint}
        }
        if len(filtered) == len(root["tickets"]):
            return data
        result = dict(data)
        result_root = dict(root)
        result_root["tickets"] = filtered
        if "sprint" in data:
            result["sprint"] = result_root
        else:
            result = result_root
        return result

    def _next_id_unlocked(self) -> str:
        return self._reserve_ids_unlocked(1)[0]

    def _reserve_ids_unlocked(self, count: int) -> list[str]:
        count = max(0, int(count))
        if count == 0:
            return []
        config = self._read_config()
        prefix = config.get("prefix", "PLF")
        first = int(config.get("next_id", 1))
        ticket_ids = [f"{prefix}-{number:03d}" for number in range(first, first + count)]
        config["next_id"] = first + count
        self._write_config(config)
        return ticket_ids

    def _archive_config(self) -> dict:
        """Return validated automatic-archive settings with safe defaults."""
        configured = self._read_config().get("archive") or {}
        if not isinstance(configured, dict):
            configured = {}
        result = dict(self.DEFAULT_ARCHIVE_CONFIG)
        result.update(configured)
        for key in (
            "max_current_tickets",
            "max_current_bytes",
            "retain_terminal_tickets",
            "retain_terminal_days",
        ):
            try:
                result[key] = max(0, int(result[key]))
            except (TypeError, ValueError):
                result[key] = self.DEFAULT_ARCHIVE_CONFIG[key]
        statuses = result.get("terminal_statuses")
        if not isinstance(statuses, list) or not statuses:
            statuses = self.DEFAULT_ARCHIVE_CONFIG["terminal_statuses"]
        result["terminal_statuses"] = {str(status).lower() for status in statuses}
        result["enabled"] = bool(result.get("enabled", True))
        return result

    @staticmethod
    def _terminal_archive_candidates(
        terminal: list[tuple[datetime, str, dict]],
        config: dict,
        *,
        capacity_triggered: bool,
        now: datetime | None = None,
    ) -> list[tuple[datetime, str, dict]]:
        """Select stale terminal tickets plus any required by the size limits.

        ``retain_terminal_days=0`` moves terminal tickets immediately. Larger
        values retain that many UTC calendar dates including today. Count
        retention only applies to capacity-driven rotation and never keeps stale
        work in the operational sprint indefinitely.
        """
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        retention_days = config["retain_terminal_days"]
        if retention_days == 0:
            selected_ids = {ticket_id for _, ticket_id, _ in terminal}
        else:
            cutoff_date = current.astimezone(timezone.utc).date() - timedelta(
                days=retention_days - 1
            )
            selected_ids = {
                ticket_id
                for timestamp, ticket_id, _ in terminal
                if timestamp.date() < cutoff_date
            }
        if capacity_triggered:
            move_count = max(0, len(terminal) - config["retain_terminal_tickets"])
            selected_ids.update(ticket_id for _, ticket_id, _ in terminal[:move_count])
        return [item for item in terminal if item[1] in selected_ids]

    @staticmethod
    def _ticket_archive_timestamp(ticket: dict) -> datetime:
        """Choose the best stable timestamp for ordering and archive naming."""
        execution = ticket.get("execution")
        values = []
        if isinstance(execution, dict):
            values.append(execution.get("finished_at"))
        values.extend((ticket.get("updated_at"), ticket.get("created_at")))
        for value in values:
            if isinstance(value, datetime):
                parsed = value
            elif isinstance(value, str) and value:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        return datetime.now(timezone.utc)

    def archive_completed(self, *, force: bool = False) -> dict:
        """Move stale terminal tickets into daily history files.

        Terminal tickets from prior UTC dates are rotated even below the current
        sprint limits. Size and count limits can rotate additional terminal work
        while retaining the configured number of recent entries. The operation is
        serialized with all other store mutations and is idempotent after an
        interrupted multi-file write. ``force`` applies count retention immediately
        without weakening the terminal-status guard.
        """
        with self.mutation_lock():
            return self._archive_completed_unlocked(force=force)

    def _archive_completed_unlocked(self, *, force: bool = False) -> dict:
        if self._uses_sharded_storage():
            return self._archive_completed_sharded_unlocked(force=force)

        from planfile.core.fastio import read_yaml_fast

        config = self._archive_config()
        current_file = self._sprint_file("current")
        report = {
            "triggered": False,
            "archived": 0,
            "remaining": 0,
            "archive_files": [],
        }
        if not config["enabled"] or not current_file.exists():
            return report

        data = read_yaml_fast(current_file) or {}
        sprint_data = data.get("sprint", data)
        tickets = sprint_data.get("tickets") or {}
        if not isinstance(tickets, dict):
            return report
        report["remaining"] = len(tickets)

        over_count = (
            config["max_current_tickets"] > 0 and len(tickets) > config["max_current_tickets"]
        )
        try:
            current_size = current_file.stat().st_size
        except OSError:
            current_size = 0
        over_size = config["max_current_bytes"] > 0 and current_size > config["max_current_bytes"]
        terminal = [
            (self._ticket_archive_timestamp(ticket), ticket_id, ticket)
            for ticket_id, ticket in tickets.items()
            if isinstance(ticket, dict)
            and str(ticket.get("status", "")).lower() in config["terminal_statuses"]
        ]
        terminal.sort(key=lambda item: (item[0], item[1]))
        selected = self._terminal_archive_candidates(
            terminal,
            config,
            capacity_triggered=force or over_count or over_size,
        )
        if not selected:
            return report
        report["triggered"] = True

        archive_data: dict[Path, dict] = {}
        moved_ids: list[str] = []
        for timestamp, ticket_id, ticket in selected:
            archive_name = f"history-{timestamp:%Y-%m-%d}"
            archive_file = self._sprint_file(archive_name)
            archive = archive_data.get(archive_file)
            if archive is None:
                archive = read_yaml_fast(archive_file) if archive_file.exists() else None
                archive = archive or {
                    "sprint": {
                        "id": archive_name,
                        "name": f"History {timestamp:%Y-%m-%d}",
                        "status": "archived",
                        "tickets": {},
                    }
                }
                archive_data[archive_file] = archive
            archive_sprint = archive.get("sprint", archive)
            archive_tickets = archive_sprint.setdefault("tickets", {})
            archived_ticket = dict(ticket)
            archived_ticket["sprint"] = archive_name
            # Overwrite makes a retry safe if a process stopped after writing the
            # archive but before removing the same ticket from current.yaml.
            archive_tickets[ticket_id] = archived_ticket
            moved_ids.append(ticket_id)

        # Write destinations first: interruption can temporarily duplicate data,
        # but can never lose a ticket. A later run removes any duplicates safely.
        for archive_file, archive in archive_data.items():
            self._write_yaml_atomic(archive_file, archive, allow_unicode=True)
            if hasattr(self, "_yaml_cache"):
                self._yaml_cache.pop(str(archive_file), None)
        self._record_history_locations_unlocked(
            {
                ticket_id: f"history-{timestamp:%Y-%m-%d}"
                for timestamp, ticket_id, _ in selected
            }
        )
        for ticket_id in moved_ids:
            tickets.pop(ticket_id, None)
        self._write_yaml_atomic(current_file, data, allow_unicode=True)
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(current_file), None)

        report["archived"] = len(moved_ids)
        report["remaining"] = len(tickets)
        report["archive_files"] = [path.stem for path in sorted(archive_data)]
        return report

    def _archive_completed_sharded_unlocked(self, *, force: bool = False) -> dict:
        storage = self._sharded_storage()
        config = self._archive_config()
        report = {
            "triggered": False,
            "archived": 0,
            "remaining": 0,
            "archive_files": [],
        }
        if not config["enabled"] or "current" not in storage.sprint_ids():
            return report

        data = storage.load_sprint("current")
        sprint_data = data.get("sprint", data)
        tickets = sprint_data.get("tickets") or {}
        if not isinstance(tickets, dict):
            return report
        report["remaining"] = len(tickets)
        over_count = (
            config["max_current_tickets"] > 0
            and len(tickets) > config["max_current_tickets"]
        )
        over_size = (
            config["max_current_bytes"] > 0
            and storage.sprint_size("current") > config["max_current_bytes"]
        )
        terminal = [
            (self._ticket_archive_timestamp(ticket), ticket_id, ticket)
            for ticket_id, ticket in tickets.items()
            if isinstance(ticket, dict)
            and str(ticket.get("status", "")).lower() in config["terminal_statuses"]
        ]
        terminal.sort(key=lambda item: (item[0], item[1]))
        selected = self._terminal_archive_candidates(
            terminal,
            config,
            capacity_triggered=force or over_count or over_size,
        )
        if not selected:
            return report
        report["triggered"] = True

        archives: dict[str, dict] = {}
        moved_ids = []
        for timestamp, ticket_id, ticket in selected:
            archive_name = f"history-{timestamp:%Y-%m-%d}"
            archive = archives.get(archive_name)
            if archive is None:
                if archive_name in storage.sprint_ids():
                    archive = storage.load_sprint(archive_name)
                else:
                    archive = {
                        "sprint": {
                            "id": archive_name,
                            "name": f"History {timestamp:%Y-%m-%d}",
                            "status": "archived",
                            "tickets": {},
                        }
                    }
                archives[archive_name] = archive
            archive_root = archive.get("sprint", archive)
            archived_ticket = dict(ticket)
            archived_ticket["sprint"] = archive_name
            archive_root.setdefault("tickets", {})[ticket_id] = archived_ticket
            moved_ids.append(ticket_id)

        for archive_name, archive in archives.items():
            storage.write_sprint(archive_name, archive)
            self._invalidate_sharded_cache(archive_name)
        self._record_history_locations_unlocked(
            {
                ticket_id: f"history-{timestamp:%Y-%m-%d}"
                for timestamp, ticket_id, _ in selected
            }
        )
        for ticket_id in moved_ids:
            tickets.pop(ticket_id, None)
        storage.write_sprint("current", data)
        self._invalidate_sharded_cache("current")

        report["archived"] = len(moved_ids)
        report["remaining"] = len(tickets)
        report["archive_files"] = sorted(archives)
        return report

    def next_id(self) -> str:
        with self.mutation_lock():
            return self._next_id_unlocked()

    # --- Override base_dir for StoreFileMixin ---
    def _sprint_file(self, sprint: str) -> Path:
        if not self.SPRINT_ID_PATTERN.fullmatch(str(sprint)):
            raise ValueError(f"invalid_sprint_id:{sprint}")
        return self._sprints_dir / f"{sprint}.yaml"

    @staticmethod
    def _sprint_sort_key(sprint: str) -> tuple[int, str]:
        """Keep operational data ahead of potentially large history scans."""
        if sprint == "current":
            return 0, sprint
        if sprint == "backlog":
            return 1, sprint
        if sprint.startswith(("history-", "archive-")):
            return 3, sprint
        return 2, sprint

    def _all_sprint_files(self) -> list[Path]:
        return sorted(
            self._sprints_dir.glob("*.yaml"),
            key=lambda path: self._sprint_sort_key(path.stem),
        )

    def _all_sprint_ids(self) -> list[str]:
        if self._uses_sharded_storage():
            return sorted(
                self._sharded_storage().sprint_ids(),
                key=self._sprint_sort_key,
            )
        return [path.stem for path in self._all_sprint_files()]

    def ticket_records(self, sprint: str = "all"):
        """Yield raw ticket dictionaries for bounded identity checks.

        Create-time deduplication only needs status and labels. Avoid building
        thousands of Pydantic models while holding the cross-process mutation
        lock.
        """
        for sprint_id in (self._all_sprint_ids() if sprint == "all" else [sprint]):
            root = self.load_sprint(sprint_id)
            for record in (root.get("tickets") or {}).values():
                if isinstance(record, dict):
                    yield record

    def _sprint_storage_files(self, sprint: str) -> list[Path]:
        self._sprint_file(sprint)  # validate
        if self._uses_sharded_storage():
            return self._sharded_storage().storage_files(sprint)
        path = self._sprint_file(sprint)
        return [path] if path.exists() else []

    def sprint_signature(self, sprint: str) -> tuple:
        """Return a cache signature for one logical sprint or all sprints."""
        sprint_ids = self._all_sprint_ids() if sprint == "all" else [sprint]
        signature = []
        for sprint_id in sprint_ids:
            files = self._sprint_storage_files(sprint_id)
            if not files:
                signature.append((sprint_id, "<missing>", -1, -1))
                continue
            for path in files:
                try:
                    stat = path.stat()
                    signature.append((sprint_id, str(path), stat.st_mtime_ns, stat.st_size))
                except FileNotFoundError:
                    signature.append((sprint_id, str(path), -1, -1))
        return tuple(signature)

    def list_sprint_summaries(self) -> list[dict]:
        if self._uses_sharded_storage():
            storage = self._sharded_storage()
            return [storage.summary(sprint) for sprint in storage.sprint_ids()]
        result = []
        from planfile.core.fastio import read_yaml_fast

        for sprint_file in self._all_sprint_files():
            data = read_yaml_fast(sprint_file) or {}
            sprint = data.get("sprint", data)
            tickets = sprint.get("tickets", {}) if isinstance(sprint, dict) else {}
            declared_id = sprint.get("id") if isinstance(sprint, dict) else None
            metadata = {
                key: value
                for key, value in sprint.items()
                if key not in {"id", "tickets"}
            } if isinstance(sprint, dict) else {}
            if declared_id and declared_id != sprint_file.stem:
                metadata["declared_id"] = declared_id
            result.append(metadata | {"id": sprint_file.stem, "ticket_count": len(tickets)})
        return result

    def create_sprint(self, sprint: str, metadata: dict) -> dict:
        """Create an empty logical sprint in the configured backend."""
        self._sprint_file(sprint)  # validate
        with self.mutation_lock():
            if sprint in self._all_sprint_ids():
                raise ValueError(f"sprint_exists:{sprint}")
            root = {"id": sprint, **metadata, "tickets": {}}
            if self._uses_sharded_storage():
                self._sharded_storage().ensure_sprint(sprint, root)
            else:
                self._write_yaml_atomic(
                    self._sprint_file(sprint),
                    {"sprint": root},
                    allow_unicode=True,
                )
        return {key: value for key, value in root.items() if key != "tickets"} | {
            "ticket_count": 0
        }

    def _invalidate_sharded_cache(self, sprint: str) -> None:
        cache = getattr(self, "_ticket_model_cache", None)
        if cache is not None:
            cache.pop(f"sharded:{sprint}", None)

    def ticket_index_enabled(self) -> bool:
        return self._storage_config().get("index") == "sqlite"

    def _sqlite_ticket_index(self):
        from planfile.core.sqlite_index import SQLiteTicketIndex

        return SQLiteTicketIndex(self._ticket_index_path)

    def _ticket_index_signature(self) -> tuple:
        return self.sprint_signature("all"), self._evidence_revision()

    @staticmethod
    def _ticket_index_signature_cache_seconds() -> float:
        """Bound source-signature reuse during a concurrent API read burst."""
        try:
            configured = float(
                os.environ.get("PLANFILE_TICKET_INDEX_SIGNATURE_CACHE_SECONDS", "0.25")
            )
        except (TypeError, ValueError):
            configured = 0.25
        return max(0.0, min(configured, 3.0))

    def _cached_ticket_index_signature(self) -> tuple:
        """Coalesce expensive filesystem scans without hiding local mutations.

        A large store may contain thousands of evidence files. FastAPI executes
        synchronous reads in parallel, so scanning that tree independently in
        every worker amplifies one dashboard refresh into CPU and I/O
        starvation. The mutation lock invalidates this process-local snapshot
        before and after every write; the short TTL bounds observation of
        changes made by another process.
        """
        now = time.monotonic()
        probe = self._ticket_index_signature_cache_probe()
        with self._ticket_index_signature_cache_lock:
            cached = self._ticket_index_signature_cache
            if (
                cached is not None
                and cached[2] == probe
                and now - cached[0] <= self._ticket_index_signature_cache_seconds()
            ):
                return cached[1]
            signature = self._ticket_index_signature()
            self._ticket_index_signature_cache = (time.monotonic(), signature, probe)
            return signature

    def _ticket_index_signature_cache_probe(self) -> tuple:
        """Cheaply detect the active-queue edits that must never wait for TTL."""
        try:
            evidence_dir_mtime = self._evidence_dir.stat().st_mtime_ns
        except OSError:
            evidence_dir_mtime = -1
        return self.sprint_signature("current"), evidence_dir_mtime

    def _invalidate_ticket_index_signature_cache(self) -> None:
        with self._ticket_index_signature_cache_lock:
            self._ticket_index_signature_cache = None

    def _ticket_index_records(self):
        from planfile.core.fastio import read_yaml_fast

        storage = self._sharded_storage() if self._uses_sharded_storage() else None
        position = 0
        for sprint_id in self._all_sprint_ids():
            if storage is not None:
                snapshot = storage.load_sprint(sprint_id)
            else:
                snapshot = read_yaml_fast(self._sprint_file(sprint_id)) or {}
            root = snapshot.get("sprint", snapshot)
            raw_tickets = root.get("tickets") or {} if isinstance(root, dict) else {}
            for raw in raw_tickets.values():
                ticket = self._ticket_from_data(raw)
                if ticket is None:
                    continue
                yield self._ticket_index_record(ticket, sprint_id, position)
                position += 1

    @staticmethod
    def _ticket_index_record(ticket: Ticket, sprint: str, position: int = 0) -> dict:
        summary_fields = {
            "id",
            "name",
            "contract_version",
            "status",
            "priority",
            "sprint",
            "labels",
            "blocked_by",
            "blocks",
            "parent",
            "children",
            "group",
            "executor",
            "execution",
            "created_at",
            "updated_at",
        }
        full = ticket.model_dump(mode="json", exclude_none=True)
        summary = ticket.model_dump(
            mode="json",
            exclude_none=True,
            include=summary_fields,
        )
        execution = full.get("execution") or {}
        source = full.get("source") or {}
        return {
            "id": ticket.id,
            "sprint": sprint,
            "status": str(full.get("status") or ""),
            "priority": str(full.get("priority") or "normal"),
            "source": source.get("tool") if isinstance(source, dict) else None,
            "queue": (
                str(execution.get("queue") or "default")
                if isinstance(execution, dict)
                else "default"
            ),
            "created_at": str(full.get("created_at") or ""),
            "updated_at": str(full.get("updated_at") or ""),
            "position": position,
            "ticket_json": json.dumps(
                full,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "summary_json": json.dumps(
                summary,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "blocked_by": list(full.get("blocked_by") or []),
        }

    def _begin_index_mutation(self) -> bool:
        if not self.ticket_index_enabled():
            return False
        signature = self._ticket_index_signature()
        return self._sqlite_ticket_index().is_current(signature)

    def _finish_index_mutation(
        self,
        was_current: bool,
        *,
        upserts: list[tuple[Ticket, str]] | None = None,
        deletes: list[str] | None = None,
    ) -> None:
        if not was_current:
            return
        records = [
            self._ticket_index_record(ticket, sprint)
            for ticket, sprint in (upserts or [])
        ]
        self._sqlite_ticket_index().apply(
            upserts=records,
            deletes=deletes or [],
            signature=self._ticket_index_signature(),
        )

    def ensure_ticket_index(self, *, force: bool = False) -> dict:
        """Ensure the disposable SQLite projection matches durable sources."""
        index = self._sqlite_ticket_index()
        if not (force or self.ticket_index_enabled()):
            return index.status()
        if not force and time.monotonic() < self._ticket_index_rebuild_deferred_until:
            raise TicketIndexContentionError(
                "ticket_index_rebuild_deferred_after_source_contention"
            )
        signature = self._ticket_index_signature()
        if not force and index.is_current(signature):
            return index.status(signature) | {"rebuilt": False}
        with self.ticket_index_rebuild_lock():
            signature = self._ticket_index_signature()
            if not force and index.is_current(signature):
                return index.status(signature) | {"rebuilt": False}
            return self._rebuild_ticket_index_unlocked(index, force=force)

    def require_current_ticket_index(self, *, signature: tuple | None = None) -> dict:
        """Validate the projection without rebuilding it on the caller's thread.

        Latency-sensitive API reads use this guard.  A stale projection is a
        maintenance condition, not permission for an arbitrary GET request to
        parse the complete durable archive.
        """
        index = self._sqlite_ticket_index()
        if not self.ticket_index_enabled():
            raise TicketIndexContentionError("ticket_index_disabled")
        if signature is None:
            signature = self._cached_ticket_index_signature()
        if not index.is_current(signature):
            raise TicketIndexContentionError("ticket_index_stale")
        return index.status(signature) | {"rebuilt": False}

    def _rebuild_ticket_index_unlocked(self, index, *, force: bool) -> dict:
        """Rebuild while the caller holds the cross-process index lock."""
        for _attempt in range(2):
            signature_before = self._ticket_index_signature()
            if not force and index.is_current(signature_before):
                return index.status(signature_before) | {"rebuilt": False}
            try:
                count = index.rebuild(self._ticket_index_records(), signature_before)
            except Exception as exc:
                import sqlite3

                if not isinstance(exc, sqlite3.DatabaseError):
                    raise
                index.reset()
                count = index.rebuild(self._ticket_index_records(), signature_before)
            signature_after = self._ticket_index_signature()
            if signature_before != signature_after:
                force = True
                continue
            self._ticket_index_rebuild_deferred_until = 0.0
            return index.status(signature_after) | {
                "rebuilt": True,
                "tickets": count,
            }
        # YAML remains authoritative. Immediate repeated rebuilds during a
        # write burst amplify contention and can exhaust an API worker. Give
        # callers a bounded window to read the durable files directly.
        self._ticket_index_rebuild_deferred_until = time.monotonic() + 5.0
        raise TicketIndexContentionError(
            "ticket_index_sources_changed_during_rebuild"
        )

    @contextmanager
    def ticket_index_rebuild_lock(self):
        """Prevent concurrent readers from materializing duplicate full rebuilds."""
        self._ticket_index_rebuild_lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._ticket_index_rebuild_lock_path.open("a+", encoding="utf-8")
        try:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
            lock_file.close()

    def configure_ticket_index(self, enabled: bool, *, before_mutation=None) -> dict:
        """Enable/disable SQLite indexing without deleting its rebuildable data."""
        with self.mutation_lock():
            if before_mutation is not None:
                before_mutation()
            config = self._read_config()
            storage = config.get("storage") or {}
            storage = dict(storage) if isinstance(storage, dict) else {}
            storage["index"] = "sqlite" if enabled else "none"
            config["storage"] = storage
            self._write_config(config)
        if enabled:
            return self.ensure_ticket_index(force=True) | {"enabled": True}
        return self.ticket_index_status()

    def ticket_index_status(self) -> dict:
        index = self._sqlite_ticket_index()
        signature = self._ticket_index_signature() if index.path.exists() else None
        return index.status(signature) | {"enabled": self.ticket_index_enabled()}

    def indexed_ticket(self, ticket_id: str, *, repair: bool = True) -> Ticket | None:
        (self.ensure_ticket_index if repair else self.require_current_ticket_index)()
        data = self._sqlite_ticket_index().get_ticket(ticket_id)
        return self._ticket_from_data(data) if data is not None else None

    def indexed_ticket_summaries(
        self,
        *,
        sprint: str,
        filters: dict,
        offset: int,
        limit: int | None,
        repair: bool = True,
        signature: tuple | None = None,
    ) -> tuple[list[dict], int]:
        if repair:
            self.ensure_ticket_index()
        else:
            self.require_current_ticket_index(signature=signature)
        return self._sqlite_ticket_index().list_summaries(
            sprint=sprint,
            filters=filters,
            offset=offset,
            limit=limit,
        )

    def indexed_ticket_payloads(
        self,
        *,
        sprint: str,
        filters: dict,
        offset: int,
        limit: int | None,
        repair: bool = True,
        signature: tuple | None = None,
    ) -> tuple[list[dict], int]:
        """Read full ticket JSON directly from the disposable SQLite projection."""
        if repair:
            self.ensure_ticket_index()
        else:
            self.require_current_ticket_index(signature=signature)
        return self._sqlite_ticket_index().list_payloads(
            sprint=sprint,
            filters=filters,
            offset=offset,
            limit=limit,
        )

    def indexed_ticket_json_response(
        self,
        *,
        sprint: str,
        filters: dict,
        offset: int,
        limit: int | None,
        repair: bool = True,
        signature: tuple | None = None,
    ) -> tuple[bytes, int, int]:
        """Render full ticket JSON from SQLite without a Python object graph."""
        if repair:
            self.ensure_ticket_index()
        else:
            self.require_current_ticket_index(signature=signature)
        return self._sqlite_ticket_index().render_payloads(
            sprint=sprint,
            filters=filters,
            offset=offset,
            limit=limit,
        )

    def indexed_ticket_json_metrics(
        self,
        *,
        sprint: str,
        filters: dict,
        offset: int,
        limit: int | None,
        repair: bool = True,
        signature: tuple | None = None,
    ) -> tuple[int, int, int]:
        """Measure a full-ticket page before materializing its JSON body."""
        if repair:
            self.ensure_ticket_index()
        else:
            self.require_current_ticket_index(signature=signature)
        return self._sqlite_ticket_index().payload_page_metrics(
            sprint=sprint,
            filters=filters,
            offset=offset,
            limit=limit,
        )

    def indexed_ticket_operational_response(
        self,
        *,
        sprint: str,
        filters: dict,
        offset: int,
        limit: int | None,
        repair: bool = True,
        signature: tuple | None = None,
    ) -> tuple[bytes, int, int]:
        """Render a bounded operational page without Python JSON object graphs."""
        if repair:
            self.ensure_ticket_index()
        else:
            self.require_current_ticket_index(signature=signature)
        return self._sqlite_ticket_index().render_operational_payloads(
            sprint=sprint,
            filters=filters,
            offset=offset,
            limit=limit,
        )

    def migrate_to_sharded_yaml(
        self,
        *,
        shard_size: int = 100,
        custom_shards: int = 16,
        before_mutation=None,
    ) -> dict:
        """Convert legacy sprint YAML files to the opt-in sharded layout.

        The backend switch happens only after every shard has been read back and
        compared. Legacy files are then moved to a timestamped recovery directory.
        """
        shard_size = max(1, int(shard_size))
        custom_shards = max(1, min(int(custom_shards), 256))
        with self.mutation_lock():
            if before_mutation is not None:
                before_mutation()
            if self._uses_sharded_storage():
                raise ValueError("storage_already_sharded")
            legacy_files = self._all_sprint_files()
            if not legacy_files:
                raise ValueError("storage_has_no_legacy_sprints")

            from planfile.core.fastio import read_yaml_fast
            from planfile.core.sharded_yaml import ShardedYamlStorage

            snapshots = {
                path.stem: read_yaml_fast(path) or {}
                for path in legacy_files
            }
            target_dirs = [
                self._sprints_dir / f"{sprint}.shards"
                for sprint in snapshots
            ]
            occupied = [path for path in target_dirs if path.exists() and any(path.iterdir())]
            if occupied:
                raise ValueError(f"sharded_target_not_empty:{occupied[0]}")

            storage = ShardedYamlStorage(
                self._sprints_dir,
                self._write_yaml_atomic,
                shard_size=shard_size,
                custom_shards=custom_shards,
            )
            created_dirs: list[Path] = []
            try:
                for sprint, snapshot in snapshots.items():
                    directory = storage.sprint_dir(sprint)
                    if not directory.exists():
                        created_dirs.append(directory)
                    storage.write_sprint(sprint, snapshot)
                    root = snapshot.get("sprint", snapshot)
                    expected = root.get("tickets") or {} if isinstance(root, dict) else {}
                    actual = storage.load_sprint(sprint)["sprint"]["tickets"]
                    if expected != actual:
                        raise RuntimeError(f"sharded_migration_verification_failed:{sprint}")
            except Exception:
                for directory in created_dirs:
                    if directory.exists():
                        shutil.rmtree(directory)
                raise

            config = self._read_config()
            previous_storage = config.get("storage") or {}
            config["storage"] = {
                "backend": "sharded-yaml",
                "shard_size": shard_size,
                "custom_shards": custom_shards,
                "index": (
                    previous_storage.get("index", "none")
                    if isinstance(previous_storage, dict)
                    else "none"
                ),
            }
            self._write_config(config)

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            backup_dir = self.base_dir / "storage-backups" / stamp / "sprints"
            backup_dir.mkdir(parents=True, exist_ok=False)
            moved = []
            for path in legacy_files:
                destination = backup_dir / path.name
                shutil.move(str(path), str(destination))
                moved.append(str(destination))
                mirror = path.with_name(path.name + ".fast.json")
                if mirror.exists():
                    shutil.move(str(mirror), str(backup_dir / mirror.name))

            if hasattr(self, "_yaml_cache"):
                self._yaml_cache.clear()
            if hasattr(self, "_ticket_model_cache"):
                self._ticket_model_cache.clear()
            return {
                "backend": "sharded-yaml",
                "shard_size": shard_size,
                "custom_shards": custom_shards,
                "sprints": len(snapshots),
                "tickets": sum(
                    len(snapshot.get("sprint", snapshot).get("tickets") or {})
                    for snapshot in snapshots.values()
                ),
                "backup_dir": str(backup_dir),
                "moved_files": moved,
            }

    def create_ticket(self, ticket: Ticket) -> Ticket:
        """Persist a ticket into the current sprint file."""
        with self.mutation_lock():
            return self._create_ticket_unlocked(ticket)

    def create_tickets_bulk(self, tickets: list[Ticket]) -> list[Ticket]:
        """Persist validated tickets with one write per affected sprint/shard."""
        if not tickets:
            return []
        with self.mutation_lock():
            return self._create_tickets_bulk_unlocked(tickets)

    def _create_tickets_bulk_unlocked(self, tickets: list[Ticket]) -> list[Ticket]:
        index_was_current = self._begin_index_mutation()
        for ticket in tickets:
            self._prepare_ticket_for_persistence(ticket)
        grouped: dict[str, list[Ticket]] = {}
        for ticket in tickets:
            grouped.setdefault(ticket.sprint or "current", []).append(ticket)

        if self._uses_sharded_storage():
            storage = self._sharded_storage()
            for sprint, sprint_tickets in grouped.items():
                storage.upsert_tickets(
                    sprint,
                    {
                        ticket.id: ticket.model_dump(mode="json", exclude_none=True)
                        for ticket in sprint_tickets
                    },
                )
                self._invalidate_sharded_cache(sprint)
        else:
            from planfile.core.fastio import read_yaml_fast

            for sprint, sprint_tickets in grouped.items():
                sprint_file = self._sprint_file(sprint)
                data = read_yaml_fast(sprint_file) or {
                    "sprint": {
                        "id": sprint,
                        "name": sprint.title(),
                        "status": "active",
                        "tickets": {},
                    }
                }
                root = data.get("sprint", data)
                stored = root.setdefault("tickets", {})
                for ticket in sprint_tickets:
                    stored[ticket.id] = ticket.model_dump(mode="json", exclude_none=True)
                data["sprint"] = root
                self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)

        self._append_operational_lines(
            [str(ticket.dsl) for ticket in tickets if ticket.dsl]
        )
        archive_report = (
            self._archive_completed_unlocked()
            if "current" in grouped
            else {"archived": 0}
        )
        if not archive_report.get("archived"):
            self._finish_index_mutation(
                index_was_current,
                upserts=[
                    (ticket, ticket.sprint or "current")
                    for ticket in tickets
                ],
            )
        return tickets

    def list_tickets(self, sprint: str = "current", **filters) -> list[Ticket]:
        """List tickets from the configured physical backend."""
        if not self._uses_sharded_storage():
            return TicketStoreMixin.list_tickets(self, sprint=sprint, **filters)

        storage = self._sharded_storage()
        sprint_ids = storage.sprint_ids() if sprint == "all" else [sprint]
        tickets: list[Ticket] = []
        cache = getattr(self, "_ticket_model_cache", None)
        if cache is None:
            cache = {}
            self._ticket_model_cache = cache
        for sprint_id in sprint_ids:
            signature = storage.signature(sprint_id)
            key = f"sharded:{sprint_id}"
            entry = cache.get(key)
            cached_ids = (ticket.id for ticket in entry[1]) if entry is not None else ()
            evidence_revision = self._ticket_evidence_revision(cached_ids)
            if (
                entry is not None
                and entry[0] == signature
                and entry[2] == evidence_revision
            ):
                tickets.extend(entry[1])
                continue
            snapshot = storage.load_sprint(sprint_id)
            root = snapshot.get("sprint", snapshot)
            ticket_data = root.get("tickets") or {}
            evidence_revision = self._ticket_evidence_revision(ticket_data.keys())
            models = tuple(self._tickets_from_sprint_data(root))
            cache[key] = (signature, models, evidence_revision)
            tickets.extend(models)
        return self._apply_filters(tickets, **filters)

    def _prepare_ticket_for_persistence(self, ticket: Ticket) -> None:
        from planfile.core.operational_dsl import line as operational_line

        if ticket.contract_version is None:
            ticket.contract_version = TICKET_CONTRACT_VERSION
        if not ticket.dsl:
            payload = ticket.model_dump(mode="json", exclude_none=True, exclude={"dsl", "history"})
            ticket.dsl = operational_line(
                timestamp=ticket.created_at,
                kind="task",
                source="planfile.ticket",
                ticket_id=ticket.id,
                actor=(ticket.source.tool if ticket.source else None) or (ticket.executor.handler if ticket.executor else None) or "system",
                oql="ticket.create",
                uri=f"planfile://tickets/{ticket.id}/command/create",
                mode="apply",
                status=str(ticket.status.value),
                correlation_id=ticket.id,
                data={"payload": payload},
            )

    def _create_ticket_unlocked(self, ticket: Ticket) -> Ticket:
        """Persist a ticket while the caller holds ``mutation_lock``."""
        index_was_current = self._begin_index_mutation()
        self._prepare_ticket_for_persistence(ticket)
        sprint = ticket.sprint or "current"
        if self._uses_sharded_storage():
            storage = self._sharded_storage()
            storage.upsert_ticket(
                sprint,
                ticket.id,
                ticket.model_dump(mode="json", exclude_none=True),
            )
            self._append_operational_line(ticket.dsl)
            self._invalidate_sharded_cache(sprint)
            archive_report = {"archived": 0}
            if sprint == "current":
                archive_report = self._archive_completed_unlocked()
            if not archive_report.get("archived"):
                self._finish_index_mutation(
                    index_was_current,
                    upserts=[(ticket, sprint)],
                )
            return ticket

        sprint_file = self._sprint_file(sprint)

        if sprint_file.exists():
            from planfile.core.fastio import read_yaml_fast

            data = read_yaml_fast(sprint_file) or {}
        else:
            data = {
                "sprint": {"id": sprint, "name": sprint.title(), "status": "active", "tickets": {}}
            }

        sprint_data = data.get("sprint", data)
        if "tickets" not in sprint_data:
            sprint_data["tickets"] = {}

        sprint_data["tickets"][ticket.id] = ticket.model_dump(mode="json", exclude_none=True)
        data["sprint"] = sprint_data

        self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
        self._append_operational_line(ticket.dsl)

        # Invalidate yaml cache
        if hasattr(self, "_yaml_cache"):
            self._yaml_cache.pop(str(sprint_file), None)

        archive_report = (
            self._archive_completed_unlocked()
            if sprint == "current"
            else {"archived": 0}
        )
        if not archive_report.get("archived"):
            self._finish_index_mutation(
                index_was_current,
                upserts=[(ticket, sprint)],
            )

        return ticket

    def get_ticket(self, ticket_id: str, *, repair_index: bool = True) -> Ticket | None:
        if self.ticket_index_enabled():
            try:
                return self.indexed_ticket(ticket_id, repair=repair_index)
            except TicketIndexContentionError:
                # SQLite is only an acceleration layer. Source contention must
                # not make an exact durable-source lookup unavailable.
                pass
        if self._uses_sharded_storage():
            storage = self._sharded_storage()
            active = storage.get_ticket("current", ticket_id)
            if active is not None:
                return self._ticket_from_data(active)
            history_sprint = self._history_locations().get(ticket_id)
            if history_sprint:
                archived = storage.get_ticket(history_sprint, ticket_id)
                if archived is not None:
                    return self._ticket_from_data(archived)
            located = storage.locate_ticket(ticket_id)
            return self._ticket_from_data(located[1]) if located is not None else None
        checked_files = set()
        current_file = self._sprint_file("current")
        current_data = self._read_yaml_cached(current_file) or {}
        checked_files.add(current_file)
        current_root = current_data.get("sprint", current_data)
        active = (current_root.get("tickets") or {}).get(ticket_id)
        if active is not None:
            return self._ticket_from_data(active)
        history_sprint = self._history_locations().get(ticket_id)
        if history_sprint:
            history_file = self._sprint_file(history_sprint)
            history_data = self._read_yaml_cached(history_file) or {}
            checked_files.add(history_file)
            history_root = history_data.get("sprint", history_data)
            archived = (history_root.get("tickets") or {}).get(ticket_id)
            if archived is not None:
                return self._ticket_from_data(archived)
        for sprint_file in self._all_sprint_files():
            if sprint_file in checked_files:
                continue
            data = self._read_yaml_cached(sprint_file)
            if not data:
                continue
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                return self._ticket_from_data(tickets[ticket_id])
        return None

    def _serialize_update_value(self, value):
        """Convert rich Python/Pydantic values into YAML-safe primitives."""
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, list):
            return [self._serialize_update_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_update_value(item) for key, item in value.items()}
        return value

    @staticmethod
    def _execution_state(ticket_data: dict) -> str | None:
        execution = ticket_data.get("execution")
        if not isinstance(execution, dict):
            return None
        return execution.get("state")

    @staticmethod
    def _detach_history_dsl(entry: dict) -> str:
        """Move the replayable line to the operational journal only.

        The same line is appended to ``events/operations.jsonl``. Keeping a
        second copy in every history entry makes sprint rewrites and snapshots
        grow with duplicated payload while history still has all audit fields
        needed for display and triage.
        """
        return str(entry.pop("dsl", "") or "")

    @classmethod
    def _build_history_entry(
        cls,
        previous: dict,
        current: dict,
        changed_keys: list[str],
        reason: str | None = None,
        actor: str | None = None,
    ) -> dict:
        previous_status = previous.get("status")
        current_status = current.get("status")
        previous_state = cls._execution_state(previous)
        current_state = cls._execution_state(current)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "update",
            "source": "planfile.store",
            "changes": changed_keys,
        }
        if previous_status != current_status:
            entry["action"] = "status_change"
            entry["status"] = current_status
            entry["previous_status"] = previous_status
        if previous_state != current_state:
            entry["execution_state"] = current_state
            entry["previous_execution_state"] = previous_state
        if reason:
            entry["reason"] = reason
        if actor:
            entry["actor"] = actor
            entry["by"] = actor  # alias for "by whom"
        from planfile.core.operational_dsl import line as operational_line

        ticket_id = str(current.get("id") or previous.get("id") or "-")
        entry["dsl"] = operational_line(
            timestamp=entry["timestamp"],
            kind="task",
            source="planfile.history",
            ticket_id=ticket_id,
            actor=actor or "system",
            oql=f"ticket.{entry['action']}",
            uri=f"planfile://tickets/{ticket_id}/command/{entry['action']}",
            mode="apply",
            status=str(current_status or current_state or "recorded"),
            correlation_id=ticket_id,
            data={"payload": {
                "changes": changed_keys,
                "reason": reason or "",
                "previous_status": previous_status,
                "status": current_status,
                "previous_execution_state": previous_state,
                "execution_state": current_state,
            }},
        )
        return entry

    def update_ticket(
        self,
        ticket_id: str,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
        **updates,
    ) -> Ticket | None:
        """Update a ticket. If status (or execution state) changes, a structured history entry
        is appended automatically, including optional `reason` (why) and `actor` (who / by whom).
        Use reason/actor (or _reason/_actor in **updates) for rich audit on status transitions.
        """
        with self.mutation_lock():
            return self._update_ticket_unlocked(
                ticket_id,
                reason=reason,
                actor=actor,
                expected_updated_at=expected_updated_at,
                **updates,
            )

    @staticmethod
    def _updated_at_instant(value: object) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _guard_expected_updated_at(
        self,
        previous: dict,
        expected_updated_at: str | None,
    ) -> None:
        if expected_updated_at is None:
            return
        projected = self._project_ticket_evidence(previous)
        actual_updated_at = projected.get("updated_at")
        actual_instant = self._updated_at_instant(actual_updated_at)
        expected_instant = self._updated_at_instant(expected_updated_at)
        if (
            actual_instant is not None
            and expected_instant is not None
            and actual_instant == expected_instant
        ):
            return
        if str(actual_updated_at or "") == str(expected_updated_at):
            return
        raise TicketUpdatedAtConflictError("ticket_updated_at_precondition_failed")

    def _guard_immutable_terminal_reopen(
        self,
        previous: dict,
        serialized_updates: dict,
    ) -> None:
        """Keep ordinary updates monotonic after done/canceled.

        Terminal-to-terminal corrections remain possible, and append-only
        evidence uses its dedicated API. What is forbidden is projecting an
        active status or execution state onto work that was already completed
        or canceled.
        """

        previous_status = str(previous.get("status") or "")
        if previous_status not in self.IMMUTABLE_TERMINAL_STATUSES:
            return

        requested_status = str(serialized_updates.get("status") or previous_status)
        if requested_status not in self.TERMINAL_STATUSES:
            raise ImmutableTerminalReopenError("immutable_terminal_reopen")

        execution_update = serialized_updates.get("execution")
        if not isinstance(execution_update, dict) or "state" not in execution_update:
            return
        requested_state = str(execution_update.get("state") or "")
        if requested_state != requested_status:
            raise ImmutableTerminalReopenError("immutable_terminal_reopen")

    def append_ticket_evidence(
        self,
        ticket_id: str,
        *,
        idempotency_key: str,
        collection: str,
        evidence: dict,
        notes: list[str] | None = None,
        artifacts: list[str] | None = None,
        reason: str,
        actor: str,
    ) -> tuple[Ticket | None, bool]:
        """Append evidence without a client-side read/modify/write race.

        Returns ``(ticket, recorded)``. A repeated idempotency key returns the
        current ticket with ``recorded=False`` and performs no write. The check
        and mutation share one store lock, so concurrent writers cannot append
        the same external-effect receipt twice.
        """

        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("evidence_idempotency_key_required")
        if len(key) > 240:
            raise ValueError("evidence_idempotency_key_too_long")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", str(collection or "")):
            raise ValueError("evidence_collection_invalid")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("evidence_payload_required")
        if not str(actor or "").strip():
            raise ValueError("evidence_actor_required")
        if not str(reason or "").strip():
            raise ValueError("evidence_reason_required")

        with self.mutation_lock():
            index_was_current = self._begin_index_mutation()
            current = self.get_ticket(ticket_id)
            if current is None:
                return None, False
            outputs = (
                current.outputs.model_dump(mode="python", exclude_none=True)
                if current.outputs
                else {}
            )
            result = outputs.get("result")
            if result is None:
                result = {}
            if not isinstance(result, dict):
                raise ValueError("ticket_output_result_not_object")
            existing = result.get(collection) or []
            if not isinstance(existing, list):
                raise ValueError("evidence_collection_not_list")

            serialized_evidence = self._serialize_update_value(evidence)
            serialized_evidence.setdefault("idempotency_key", key)
            for item in existing:
                if self._evidence_item_key(item) != key:
                    continue
                normalized_existing = self._serialize_update_value(item)
                normalized_existing.setdefault("idempotency_key", key)
                if normalized_existing != serialized_evidence:
                    raise ValueError("evidence_idempotency_conflict")
                return current, False

            timestamp = datetime.now(timezone.utc).isoformat()
            event = {
                "schema": "planfile.ticket-evidence-event/v1",
                "timestamp": timestamp,
                "ticket_id": ticket_id,
                "idempotency_key": key,
                "collection": collection,
                "evidence": serialized_evidence,
                "notes": list(dict.fromkeys(str(item) for item in notes or [] if str(item))),
                "artifacts": list(dict.fromkeys(str(item) for item in artifacts or [] if str(item))),
                "actor": str(actor),
                "reason": str(reason),
            }
            self._append_ticket_evidence_event(ticket_id, event)
            from planfile.core.operational_dsl import line as operational_line

            self._append_operational_line(
                operational_line(
                    timestamp=timestamp,
                    kind="evidence",
                    source="planfile.evidence",
                    ticket_id=ticket_id,
                    actor=str(actor),
                    oql="ticket.evidence.append",
                    uri=f"planfile://tickets/{ticket_id}/evidence/{collection}/append",
                    mode="apply",
                    status="recorded",
                    correlation_id=ticket_id,
                    receipt_ref=f"evidence://{ticket_id}/{key}",
                    replayable=False,
                    data={
                        "payload": {
                            "collection": collection,
                            "idempotency_key": key,
                            "reason": str(reason),
                            "evidence_keys": sorted(serialized_evidence),
                        }
                    },
                )
            )
            projected = self._apply_ticket_evidence_events(
                current.model_dump(mode="json", exclude_none=True),
                [event],
            )
            model = self._ticket_from_data(projected)
            if model is not None:
                self._finish_index_mutation(
                    index_was_current,
                    upserts=[(model, model.sprint or "current")],
                )
            return model, True

    def _update_ticket_unlocked(
        self,
        ticket_id: str,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
        **updates,
    ) -> Ticket | None:
        index_was_current = self._begin_index_mutation()
        if self._uses_sharded_storage():
            return self._update_ticket_sharded_unlocked(
                ticket_id,
                reason=reason,
                actor=actor,
                expected_updated_at=expected_updated_at,
                _index_was_current=index_was_current,
                **updates,
            )

        from planfile.core.fastio import read_yaml_fast

        for sprint_file in self._all_sprint_files():
            data = read_yaml_fast(sprint_file) or {}
            sprint_data = data.get("sprint", data)
            tickets = sprint_data.get("tickets", {})
            if ticket_id in tickets:
                previous = dict(tickets[ticket_id])
                self._guard_expected_updated_at(previous, expected_updated_at)
                # Extract history metadata (reason=why the change, actor/by=who performed it)
                # Support both named params (from high-level methods) and _-prefixed or bare in updates
                history_reason = (
                    reason or updates.pop("reason", None) or updates.pop("_reason", None)
                )
                history_actor = actor or updates.pop("actor", None) or updates.pop("_actor", None)

                serialized_updates = {
                    key: self._serialize_update_value(value) for key, value in updates.items()
                }
                self._guard_immutable_terminal_reopen(previous, serialized_updates)
                terminal_status = serialized_updates.get("status")
                if terminal_status in {"done", "canceled", "blocked", "failed"}:
                    execution_update = serialized_updates.get("execution")
                    if not isinstance(execution_update, dict):
                        execution_update = dict(previous.get("execution") or {})
                    else:
                        execution_update = dict(execution_update)
                    execution_update["state"] = terminal_status
                    execution_update["assigned_to"] = None
                    execution_update["lease_expires_at"] = None
                    execution_update["finished_at"] = datetime.now(timezone.utc).isoformat()
                    serialized_updates["execution"] = execution_update
                tickets[ticket_id].update(serialized_updates)
                tickets[ticket_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                changed_keys = sorted(
                    key
                    for key, value in serialized_updates.items()
                    if key != "history" and previous.get(key) != value
                )
                if changed_keys and "history" not in serialized_updates:
                    history = list(tickets[ticket_id].get("history") or [])
                    entry = self._build_history_entry(
                        previous,
                        tickets[ticket_id],
                        changed_keys,
                        reason=history_reason,
                        actor=history_actor,
                    )
                    operational_dsl = self._detach_history_dsl(entry)
                    history.append(entry)
                    tickets[ticket_id]["history"] = history[-200:]
                self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                if changed_keys and "history" not in serialized_updates:
                    self._append_operational_line(operational_dsl)
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)
                updated_ticket = dict(tickets[ticket_id])
                archive_report = (
                    self._archive_completed_unlocked()
                    if sprint_file == self._sprint_file("current")
                    else {"archived": 0}
                )
                model = self._ticket_from_data(updated_ticket)
                if model is not None and not archive_report.get("archived"):
                    self._finish_index_mutation(
                        index_was_current,
                        upserts=[(model, sprint_file.stem)],
                    )
                return model
        return None

    def _update_ticket_sharded_unlocked(
        self,
        ticket_id: str,
        reason: str | None = None,
        actor: str | None = None,
        expected_updated_at: str | None = None,
        _index_was_current: bool = False,
        **updates,
    ) -> Ticket | None:
        storage = self._sharded_storage()
        located = storage.locate_ticket(ticket_id)
        if located is None:
            return None
        sprint, ticket_data = located
        previous = dict(ticket_data)
        self._guard_expected_updated_at(previous, expected_updated_at)
        history_reason = reason or updates.pop("reason", None) or updates.pop("_reason", None)
        history_actor = actor or updates.pop("actor", None) or updates.pop("_actor", None)
        serialized_updates = {
            key: self._serialize_update_value(value) for key, value in updates.items()
        }
        self._guard_immutable_terminal_reopen(previous, serialized_updates)
        terminal_status = serialized_updates.get("status")
        if terminal_status in {"done", "canceled", "blocked", "failed"}:
            execution_update = serialized_updates.get("execution")
            if not isinstance(execution_update, dict):
                execution_update = dict(previous.get("execution") or {})
            else:
                execution_update = dict(execution_update)
            execution_update["state"] = terminal_status
            execution_update["assigned_to"] = None
            execution_update["lease_expires_at"] = None
            execution_update["finished_at"] = datetime.now(timezone.utc).isoformat()
            serialized_updates["execution"] = execution_update

        current = dict(previous)
        current.update(serialized_updates)
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        changed_keys = sorted(
            key
            for key, value in serialized_updates.items()
            if key != "history" and previous.get(key) != value
        )
        operational_dsl = ""
        if changed_keys and "history" not in serialized_updates:
            history = list(current.get("history") or [])
            entry = self._build_history_entry(
                previous,
                current,
                changed_keys,
                reason=history_reason,
                actor=history_actor,
            )
            operational_dsl = self._detach_history_dsl(entry)
            history.append(entry)
            current["history"] = history[-200:]

        storage.upsert_ticket(sprint, ticket_id, current)
        if changed_keys and "history" not in serialized_updates:
            self._append_operational_line(operational_dsl)
        self._invalidate_sharded_cache(sprint)
        archive_report = (
            self._archive_completed_unlocked()
            if sprint == "current"
            else {"archived": 0}
        )
        model = self._ticket_from_data(current)
        if model is not None and not archive_report.get("archived"):
            self._finish_index_mutation(
                _index_was_current,
                upserts=[(model, sprint)],
            )
        return model

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a ticket by ID. Returns True if deleted, False if not found."""
        if self._uses_sharded_storage():
            with self.mutation_lock():
                index_was_current = self._begin_index_mutation()
                storage = self._sharded_storage()
                located = storage.locate_ticket(ticket_id)
                if located is None:
                    return False
                sprint, deleted_ticket = located
                storage.delete_ticket(sprint, ticket_id)
                from planfile.core.operational_dsl import line as operational_line

                self._append_operational_line(operational_line(
                    kind="task", source="planfile.store", ticket_id=ticket_id,
                    actor="planfile.store", oql="ticket.delete",
                    uri=f"planfile://tickets/{ticket_id}/command/delete", mode="apply",
                    status="deleted", replayable=False, correlation_id=ticket_id,
                    data={"payload": {
                        "name": deleted_ticket.get("name"),
                        "status": deleted_ticket.get("status"),
                    }},
                ))
                self._invalidate_sharded_cache(sprint)
                self._finish_index_mutation(
                    index_was_current,
                    deletes=[ticket_id],
                )
                return True

        from planfile.core.fastio import read_yaml_fast

        with self.mutation_lock():
            index_was_current = self._begin_index_mutation()
            for sprint_file in self._all_sprint_files():
                data = read_yaml_fast(sprint_file) or {}
                sprint_data = data.get("sprint", data)
                tickets = sprint_data.get("tickets", {})
                if ticket_id in tickets:
                    from planfile.core.operational_dsl import line as operational_line

                    deleted_ticket = dict(tickets[ticket_id])
                    del tickets[ticket_id]
                    self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                    self._append_operational_line(operational_line(
                        kind="task", source="planfile.store", ticket_id=ticket_id,
                        actor="planfile.store", oql="ticket.delete",
                        uri=f"planfile://tickets/{ticket_id}/command/delete", mode="apply",
                        status="deleted", replayable=False, correlation_id=ticket_id,
                        data={"payload": {"name": deleted_ticket.get("name"), "status": deleted_ticket.get("status")}},
                    ))
                    if hasattr(self, "_yaml_cache"):
                        self._yaml_cache.pop(str(sprint_file), None)
                    self._finish_index_mutation(
                        index_was_current,
                        deletes=[ticket_id],
                    )
                    return True
        return False

    def move_ticket(self, ticket_id: str, to_sprint: str) -> bool:
        """Move a ticket under one lock, rolling back if source removal fails."""
        self._sprint_file(to_sprint)  # validate
        if self._uses_sharded_storage():
            with self.mutation_lock():
                index_was_current = self._begin_index_mutation()
                storage = self._sharded_storage()
                located = storage.locate_ticket(ticket_id)
                if located is None:
                    return False
                source_sprint, previous_ticket = located
                if source_sprint == to_sprint:
                    return True
                if storage.get_ticket(to_sprint, ticket_id) is not None:
                    raise ValueError(f"ticket_exists_in_target_sprint:{ticket_id}:{to_sprint}")

                moved_ticket = dict(previous_ticket)
                moved_ticket["sprint"] = to_sprint
                moved_ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
                history = list(moved_ticket.get("history") or [])
                entry = self._build_history_entry(
                    previous_ticket,
                    moved_ticket,
                    ["sprint"],
                    reason="move_ticket",
                )
                operational_dsl = self._detach_history_dsl(entry)
                history.append(entry)
                moved_ticket["history"] = history[-200:]

                storage.upsert_ticket(to_sprint, ticket_id, moved_ticket)
                try:
                    removed = storage.delete_ticket(source_sprint, ticket_id)
                    if removed is None:
                        raise RuntimeError(f"ticket_disappeared_during_move:{ticket_id}")
                except Exception:
                    storage.delete_ticket(to_sprint, ticket_id)
                    raise
                self._invalidate_sharded_cache(source_sprint)
                self._invalidate_sharded_cache(to_sprint)
                self._append_operational_line(operational_dsl)
                model = self._ticket_from_data(moved_ticket)
                if model is not None:
                    self._finish_index_mutation(
                        index_was_current,
                        upserts=[(model, to_sprint)],
                    )
                return True

        from planfile.core.fastio import read_yaml_fast

        destination_file = self._sprint_file(to_sprint)
        with self.mutation_lock():
            index_was_current = self._begin_index_mutation()
            for source_file in self._all_sprint_files():
                source_data = read_yaml_fast(source_file) or {}
                source_root = source_data.get("sprint", source_data)
                source_tickets = source_root.get("tickets", {})
                if ticket_id not in source_tickets:
                    continue
                if source_file == destination_file:
                    return True

                previous_ticket = dict(source_tickets[ticket_id])
                moved_ticket = dict(previous_ticket)
                moved_ticket["sprint"] = to_sprint
                moved_ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
                history = list(moved_ticket.get("history") or [])
                entry = self._build_history_entry(
                    previous_ticket,
                    moved_ticket,
                    ["sprint"],
                    reason="move_ticket",
                )
                operational_dsl = self._detach_history_dsl(entry)
                history.append(entry)
                moved_ticket["history"] = history[-200:]

                destination_existed = destination_file.exists()
                destination_before = read_yaml_fast(destination_file) if destination_existed else None
                destination_data = destination_before or {
                    "sprint": {
                        "id": to_sprint,
                        "name": to_sprint.replace("-", " ").title(),
                        "status": "active",
                        "tickets": {},
                    }
                }
                destination_root = destination_data.get("sprint", destination_data)
                destination_tickets = destination_root.setdefault("tickets", {})
                if ticket_id in destination_tickets:
                    raise ValueError(f"ticket_exists_in_target_sprint:{ticket_id}:{to_sprint}")
                destination_tickets[ticket_id] = moved_ticket
                destination_data["sprint"] = destination_root

                self._write_yaml_atomic(destination_file, destination_data, allow_unicode=True)
                try:
                    del source_tickets[ticket_id]
                    self._write_yaml_atomic(source_file, source_data, allow_unicode=True)
                except Exception:
                    if destination_existed and destination_before is not None:
                        self._write_yaml_atomic(destination_file, destination_before, allow_unicode=True)
                    else:
                        destination_file.unlink(missing_ok=True)
                    raise
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(source_file), None)
                    self._yaml_cache.pop(str(destination_file), None)
                self._append_operational_line(operational_dsl)
                model = self._ticket_from_data(moved_ticket)
                if model is not None:
                    self._finish_index_mutation(
                        index_was_current,
                        upserts=[(model, to_sprint)],
                    )
                return True
        return False

    def delete_tickets_bulk(self, ticket_ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple tickets by ID. Returns (deleted_ids, not_found_ids)."""
        if self._uses_sharded_storage():
            deleted: list[str] = []
            not_found: list[str] = []
            deleted_tickets: dict[str, dict] = {}
            changed_sprints: set[str] = set()
            with self.mutation_lock():
                index_was_current = self._begin_index_mutation()
                storage = self._sharded_storage()
                for ticket_id in ticket_ids:
                    located = storage.locate_ticket(ticket_id)
                    if located is None:
                        not_found.append(ticket_id)
                        continue
                    sprint, ticket = located
                    removed = storage.delete_ticket(sprint, ticket_id)
                    if removed is None:
                        not_found.append(ticket_id)
                        continue
                    deleted.append(ticket_id)
                    deleted_tickets[ticket_id] = ticket
                    changed_sprints.add(sprint)
                from planfile.core.operational_dsl import line as operational_line

                for ticket_id in deleted:
                    deleted_ticket = deleted_tickets[ticket_id]
                    self._append_operational_line(operational_line(
                        kind="task", source="planfile.store", ticket_id=ticket_id,
                        actor="planfile.store", oql="ticket.delete",
                        uri=f"planfile://tickets/{ticket_id}/command/delete", mode="apply",
                        status="deleted", replayable=False, correlation_id=ticket_id,
                        data={"payload": {
                            "name": deleted_ticket.get("name"),
                            "status": deleted_ticket.get("status"),
                        }},
                    ))
                for sprint in changed_sprints:
                    self._invalidate_sharded_cache(sprint)
                self._finish_index_mutation(
                    index_was_current,
                    deletes=deleted,
                )
            return deleted, not_found

        deleted = []
        not_found = []

        with self.mutation_lock():
            index_was_current = self._begin_index_mutation()
            # Load all sprint files into memory
            from planfile.core.fastio import read_yaml_fast

            sprint_contents = {}
            for sprint_file in self._all_sprint_files():
                sprint_contents[sprint_file] = read_yaml_fast(sprint_file) or {}

            modified_files = set()
            deleted_tickets: dict[str, dict] = {}

            for ticket_id in ticket_ids:
                found = False
                for sprint_file, data in sprint_contents.items():
                    sprint_data = data.get("sprint", data)
                    tickets = sprint_data.get("tickets", {})
                    if isinstance(tickets, dict) and ticket_id in tickets:
                        deleted_tickets[ticket_id] = dict(tickets[ticket_id])
                        del tickets[ticket_id]
                        modified_files.add(sprint_file)
                        deleted.append(ticket_id)
                        found = True
                        break
                if not found:
                    not_found.append(ticket_id)

            # Write only the modified sprint files back to disk, exactly once!
            for sprint_file in modified_files:
                data = sprint_contents[sprint_file]
                self._write_yaml_atomic(sprint_file, data, allow_unicode=True)
                if hasattr(self, "_yaml_cache"):
                    self._yaml_cache.pop(str(sprint_file), None)

            from planfile.core.operational_dsl import line as operational_line
            for ticket_id in deleted:
                deleted_ticket = deleted_tickets[ticket_id]
                self._append_operational_line(operational_line(
                    kind="task", source="planfile.store", ticket_id=ticket_id,
                    actor="planfile.store", oql="ticket.delete",
                    uri=f"planfile://tickets/{ticket_id}/command/delete", mode="apply",
                    status="deleted", replayable=False, correlation_id=ticket_id,
                    data={"payload": {"name": deleted_ticket.get("name"), "status": deleted_ticket.get("status")}},
                ))
            self._finish_index_mutation(
                index_was_current,
                deletes=deleted,
            )

        return deleted, not_found


PlanfileStore = Store
