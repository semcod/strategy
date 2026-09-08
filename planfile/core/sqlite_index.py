"""Disposable SQLite materialized index for Planfile ticket snapshots."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterable
from itertools import islice
from pathlib import Path
from typing import Any

SQLITE_INDEX_SCHEMA = "planfile.sqlite-ticket-index/v1"
_SCHEMA_VERSION = 1
_REBUILD_BATCH_SIZE = 128
_SOURCE_INDEXED_AT_NS_KEY = "source_indexed_at_ns"


class SQLiteTicketIndex:
    """Indexed projection of YAML/JSONL sources.

    The database is never the only copy of a ticket. A corrupt, missing or stale
    index can be deleted and rebuilt from the durable Planfile files.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @staticmethod
    def serialize_signature(signature: tuple) -> str:
        return json.dumps(signature, ensure_ascii=False, separators=(",", ":"))

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if str(journal_mode).lower() != "wal":
            connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        initialized = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
        ).fetchone()
        if initialized is None:
            self._initialize(connection)
        return connection

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                sprint TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                source TEXT,
                queue TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                position INTEGER NOT NULL,
                ticket_json TEXT NOT NULL,
                summary_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS tickets_sprint_position
                ON tickets(sprint, position);
            CREATE INDEX IF NOT EXISTS tickets_sprint_status_priority
                ON tickets(sprint, status, priority, position);
            CREATE INDEX IF NOT EXISTS tickets_source
                ON tickets(source, position);
            CREATE TABLE IF NOT EXISTS dependencies (
                ticket_id TEXT NOT NULL,
                blocked_by TEXT NOT NULL,
                PRIMARY KEY(ticket_id, blocked_by),
                FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS dependencies_blocked_by
                ON dependencies(blocked_by);
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema', ?)",
            (SQLITE_INDEX_SCHEMA,),
        )
        connection.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(_SCHEMA_VERSION),),
        )
        connection.commit()

    def is_current(self, signature: tuple) -> bool:
        if not self.path.exists():
            return False
        expected = self.serialize_signature(signature)
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM meta WHERE key='source_signature'"
                ).fetchone()
                return row is not None and row["value"] == expected
        except sqlite3.DatabaseError:
            return False

    def rebuild(
        self,
        records: Iterable[dict[str, Any]],
        signature: tuple,
        *,
        batch_size: int = _REBUILD_BATCH_SIZE,
    ) -> int:
        """Atomically replace the index while retaining one bounded batch.

        Durable Planfile stores can contain hundreds of megabytes of serialized
        tickets.  Materializing the whole iterable here duplicates the object
        graph already produced by the store and makes a disposable rebuild the
        largest memory consumer in the service.
        """
        if batch_size < 1:
            raise ValueError("ticket_index_rebuild_batch_size_invalid")
        rows = iter(records)
        count = 0
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM dependencies")
            connection.execute("DELETE FROM tickets")
            while True:
                batch = list(islice(rows, batch_size))
                if not batch:
                    break
                connection.executemany(
                    """
                    INSERT INTO tickets(
                        id, sprint, status, priority, source, queue,
                        created_at, updated_at, position, ticket_json, summary_json
                    ) VALUES(
                        :id, :sprint, :status, :priority, :source, :queue,
                        :created_at, :updated_at, :position, :ticket_json, :summary_json
                    )
                    """,
                    batch,
                )
                connection.executemany(
                    "INSERT INTO dependencies(ticket_id, blocked_by) VALUES(?, ?)",
                    (
                        (row["id"], dependency)
                        for row in batch
                        for dependency in row.get("blocked_by", [])
                    ),
                )
                count += len(batch)
                # Release record graphs before constructing the next batch.
                batch.clear()
            connection.execute(
                """
                INSERT INTO meta(key, value) VALUES('source_signature', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (self.serialize_signature(signature),),
            )
            connection.execute(
                """
                INSERT INTO meta(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (_SOURCE_INDEXED_AT_NS_KEY, str(time.time_ns())),
            )
            connection.commit()
        return count

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ticket_json FROM tickets WHERE id=?",
                (ticket_id,),
            ).fetchone()
        return json.loads(row["ticket_json"]) if row is not None else None

    def apply(
        self,
        *,
        upserts: Iterable[dict[str, Any]] = (),
        deletes: Iterable[str] = (),
        signature: tuple,
    ) -> None:
        """Apply a known-complete store mutation and advance its source signature."""
        rows = list(upserts)
        deleted_ids = list(deletes)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if deleted_ids:
                connection.executemany(
                    "DELETE FROM tickets WHERE id=?",
                    [(ticket_id,) for ticket_id in deleted_ids],
                )
            next_position = int(
                connection.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS value FROM tickets"
                ).fetchone()["value"]
            )
            for row in rows:
                existing = connection.execute(
                    "SELECT position FROM tickets WHERE id=?",
                    (row["id"],),
                ).fetchone()
                position = existing["position"] if existing is not None else next_position
                if existing is None:
                    next_position += 1
                values = dict(row)
                values["position"] = position
                connection.execute(
                    """
                    INSERT INTO tickets(
                        id, sprint, status, priority, source, queue,
                        created_at, updated_at, position, ticket_json, summary_json
                    ) VALUES(
                        :id, :sprint, :status, :priority, :source, :queue,
                        :created_at, :updated_at, :position, :ticket_json, :summary_json
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        sprint=excluded.sprint,
                        status=excluded.status,
                        priority=excluded.priority,
                        source=excluded.source,
                        queue=excluded.queue,
                        created_at=excluded.created_at,
                        updated_at=excluded.updated_at,
                        ticket_json=excluded.ticket_json,
                        summary_json=excluded.summary_json
                    """,
                    values,
                )
                connection.execute(
                    "DELETE FROM dependencies WHERE ticket_id=?",
                    (row["id"],),
                )
                connection.executemany(
                    "INSERT INTO dependencies(ticket_id, blocked_by) VALUES(?, ?)",
                    [(row["id"], dependency) for dependency in row.get("blocked_by", [])],
                )
            connection.execute(
                """
                INSERT INTO meta(key, value) VALUES('source_signature', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (self.serialize_signature(signature),),
            )
            connection.execute(
                """
                INSERT INTO meta(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (_SOURCE_INDEXED_AT_NS_KEY, str(time.time_ns())),
            )
            connection.commit()

    def has_fresh_snapshot(self, max_age_seconds: float) -> bool:
        """Return whether the last atomic projection is recent enough to serve stale.

        The source signature may stop matching while a durable mutation or a
        background rebuild is in progress.  The committed SQLite transaction is
        still a coherent last-known-good snapshot, but only for a bounded window.
        """
        if max_age_seconds < 0 or not self.path.exists():
            return False
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT key, value FROM meta WHERE key IN ('source_signature', ?)",
                    (_SOURCE_INDEXED_AT_NS_KEY,),
                ).fetchall()
            metadata = {row["key"]: row["value"] for row in rows}
            if "source_signature" not in metadata:
                return False
            indexed_at_ns = int(metadata[_SOURCE_INDEXED_AT_NS_KEY])
            age_ns = time.time_ns() - indexed_at_ns
            return 0 <= age_ns <= int(max_age_seconds * 1_000_000_000)
        except (KeyError, OSError, sqlite3.DatabaseError, TypeError, ValueError):
            return False

    def list_summaries(
        self,
        *,
        sprint: str,
        filters: dict[str, Any],
        offset: int,
        limit: int | None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = []
        parameters: list[Any] = []
        if sprint != "all":
            conditions.append("sprint=?")
            parameters.append(sprint)
        for key in ("status", "priority", "source"):
            value = filters.get(key)
            if value is None:
                continue
            conditions.append(f"{key}=?")
            parameters.append(str(getattr(value, "value", value)))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM tickets{where}",
                    parameters,
                ).fetchone()["count"]
            )
            sql = f"SELECT summary_json FROM tickets{where} ORDER BY position"
            page_parameters = list(parameters)
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                page_parameters.extend((limit, offset))
            elif offset:
                sql += " LIMIT -1 OFFSET ?"
                page_parameters.append(offset)
            rows = connection.execute(sql, page_parameters).fetchall()
        return [json.loads(row["summary_json"]) for row in rows], total

    def list_payloads(
        self,
        *,
        sprint: str,
        filters: dict[str, Any],
        offset: int,
        limit: int | None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return full ticket payloads without materializing Pydantic models."""
        conditions = []
        parameters: list[Any] = []
        if sprint != "all":
            conditions.append("sprint=?")
            parameters.append(sprint)
        for key in ("status", "priority", "source"):
            value = filters.get(key)
            if value is None:
                continue
            conditions.append(f"{key}=?")
            parameters.append(str(getattr(value, "value", value)))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM tickets{where}",
                    parameters,
                ).fetchone()["count"]
            )
            sql = f"SELECT ticket_json FROM tickets{where} ORDER BY position"
            page_parameters = list(parameters)
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                page_parameters.extend((limit, offset))
            elif offset:
                sql += " LIMIT -1 OFFSET ?"
                page_parameters.append(offset)
            rows = connection.execute(sql, page_parameters).fetchall()
        return [json.loads(row["ticket_json"]) for row in rows], total

    def render_payloads(
        self,
        *,
        sprint: str,
        filters: dict[str, Any],
        offset: int,
        limit: int | None,
    ) -> tuple[bytes, int, int]:
        """Render a full JSON array directly from stored canonical ticket JSON."""
        conditions = []
        parameters: list[Any] = []
        if sprint != "all":
            conditions.append("sprint=?")
            parameters.append(sprint)
        for key in ("status", "priority", "source"):
            value = filters.get(key)
            if value is None:
                continue
            conditions.append(f"{key}=?")
            parameters.append(str(getattr(value, "value", value)))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM tickets{where}",
                    parameters,
                ).fetchone()["count"]
            )
            sql = f"SELECT ticket_json FROM tickets{where} ORDER BY position"
            page_parameters = list(parameters)
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                page_parameters.extend((limit, offset))
            elif offset:
                sql += " LIMIT -1 OFFSET ?"
                page_parameters.append(offset)
            cursor = connection.execute(sql, page_parameters)
            body = bytearray(b"[")
            count = 0
            for row in cursor:
                if count:
                    body.extend(b",")
                body.extend(row["ticket_json"].encode("utf-8"))
                count += 1
            body.extend(b"]")
        return bytes(body), total, count

    def render_operational_payloads(
        self,
        *,
        sprint: str,
        filters: dict[str, Any],
        offset: int,
        limit: int | None,
    ) -> tuple[bytes, int, int]:
        """Project and render queue payloads inside SQLite's JSON runtime."""
        conditions = []
        parameters: list[Any] = []
        if sprint != "all":
            conditions.append("sprint=?")
            parameters.append(sprint)
        for key in ("status", "priority", "source"):
            value = filters.get(key)
            if value is None:
                continue
            conditions.append(f"{key}=?")
            parameters.append(str(getattr(value, "value", value)))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        page_sql = f"SELECT position, ticket_json FROM tickets{where} ORDER BY position"
        page_parameters = list(parameters)
        if limit is not None:
            page_sql += " LIMIT ? OFFSET ?"
            page_parameters.extend((limit, offset))
        elif offset:
            page_sql += " LIMIT -1 OFFSET ?"
            page_parameters.append(offset)
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM tickets{where}",
                    parameters,
                ).fetchone()["count"]
            )
            cursor = connection.execute(
                """
                WITH page AS (
                    """ + page_sql + """
                ), stripped AS (
                    SELECT position, json_remove(
                        ticket_json,
                        '$.history', '$.dsl', '$.file', '$.files',
                        '$.integration', '$.llm_hints', '$.sync',
                        '$.source.context', '$.outputs.notes', '$.outputs.artifacts'
                    ) AS payload
                    FROM page
                ), without_empty_source AS (
                    SELECT position,
                        CASE WHEN json_extract(payload, '$.source') = '{}'
                            THEN json_remove(payload, '$.source') ELSE payload END AS payload
                    FROM stripped
                ), normalized AS (
                    SELECT position,
                        CASE WHEN json_extract(payload, '$.outputs') = '{}'
                            THEN json_remove(payload, '$.outputs') ELSE payload END AS payload
                    FROM without_empty_source
                )
                SELECT payload FROM normalized ORDER BY position
                """,
                page_parameters,
            )
            body = bytearray(b"[")
            count = 0
            for row in cursor:
                if count:
                    body.extend(b",")
                body.extend(row["payload"].encode("utf-8"))
                count += 1
            body.extend(b"]")
        return bytes(body), total, count

    def payload_page_metrics(
        self,
        *,
        sprint: str,
        filters: dict[str, Any],
        offset: int,
        limit: int | None,
    ) -> tuple[int, int, int]:
        """Return total rows, selected rows and exact JSON-array bytes."""
        conditions = []
        parameters: list[Any] = []
        if sprint != "all":
            conditions.append("sprint=?")
            parameters.append(sprint)
        for key in ("status", "priority", "source"):
            value = filters.get(key)
            if value is None:
                continue
            conditions.append(f"{key}=?")
            parameters.append(str(getattr(value, "value", value)))
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM tickets{where}",
                    parameters,
                ).fetchone()["count"]
            )
            sql = f"SELECT ticket_json FROM tickets{where} ORDER BY position"
            page_parameters = list(parameters)
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                page_parameters.extend((limit, offset))
            elif offset:
                sql += " LIMIT -1 OFFSET ?"
                page_parameters.append(offset)
            row = connection.execute(
                "SELECT COUNT(*) AS count, "
                "COALESCE(SUM(LENGTH(CAST(ticket_json AS BLOB))), 0) AS bytes "
                f"FROM ({sql})",
                page_parameters,
            ).fetchone()
        count = int(row["count"])
        array_bytes = int(row["bytes"]) + max(0, count - 1) + 2
        return total, count, array_bytes

    def status(self, signature: tuple | None = None) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": SQLITE_INDEX_SCHEMA,
                "exists": False,
                "current": False,
                "tickets": 0,
                "bytes": 0,
                "path": str(self.path),
            }
        try:
            with self._connect() as connection:
                count = int(
                    connection.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()[
                        "count"
                    ]
                )
                row = connection.execute(
                    "SELECT value FROM meta WHERE key='source_signature'"
                ).fetchone()
            current = (
                signature is not None
                and row is not None
                and row["value"] == self.serialize_signature(signature)
            )
            return {
                "schema": SQLITE_INDEX_SCHEMA,
                "exists": True,
                "current": current,
                "tickets": count,
                "bytes": self.path.stat().st_size,
                "path": str(self.path),
            }
        except (OSError, sqlite3.DatabaseError) as exc:
            return {
                "schema": SQLITE_INDEX_SCHEMA,
                "exists": True,
                "current": False,
                "tickets": 0,
                "bytes": 0,
                "path": str(self.path),
                "error": str(exc),
            }

    def reset(self) -> None:
        """Delete only disposable SQLite index files."""
        for path in (
            self.path,
            self.path.with_name(self.path.name + "-wal"),
            self.path.with_name(self.path.name + "-shm"),
        ):
            path.unlink(missing_ok=True)
