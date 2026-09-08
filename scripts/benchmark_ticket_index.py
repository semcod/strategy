#!/usr/bin/env python3
"""Measure SQLite materialized-index build and query costs."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from benchmark_ticket_storage import _prepare, _snapshot
from fastapi.testclient import TestClient

from planfile.api import server


def _median_ms(action, repeats: int = 1):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = action()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples), result


def _summary_without_index(pf, limit: int):
    fields = {"id", "name", "status", "priority", "execution", "updated_at"}
    return [
        ticket.model_dump(mode="json", exclude_none=True, include=fields)
        for ticket in pf.list_tickets(sprint="current")[:limit]
    ]


def _rss_kib() -> int:
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def _stale_read_availability(pf, *, repeats: int = 25) -> dict:
    """Measure request latency/RSS while background repair is pending."""
    server.get_planfile = lambda: pf
    server._TICKET_LIST_RESPONSE_CACHE.clear()
    server._TICKET_LIST_LATEST.clear()
    client = TestClient(server.app)
    query = "/tickets?sprint=all&status=open&limit=500&view=summary"
    primed = client.get(query)
    primed.raise_for_status()

    pf.store._evidence_dir.mkdir(parents=True, exist_ok=True)
    (pf.store._evidence_dir / "benchmark-external.jsonl").write_text(
        '{"benchmark":"external-signature-change"}\n',
        encoding="utf-8",
    )

    rss_before = _rss_kib()
    samples = []
    states = []
    statuses = []
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.get(query)
        samples.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)
        states.append(response.headers.get("X-Planfile-Index-State"))
    rss_after = _rss_kib()
    samples.sort()
    p95_index = min(len(samples) - 1, max(0, int(len(samples) * 0.95)))
    return {
        "requests": repeats,
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(samples[p95_index], 3),
        "rss_delta_kib": rss_after - rss_before,
        "statuses": sorted(set(statuses)),
        "index_states": sorted({state or "current" for state in states}),
    }


def _measure(root: Path, ticket_count: int, *, shard_size: int | None) -> dict:
    pf = _prepare(root, _snapshot(ticket_count))
    backend = "single-yaml"
    migration_ms = None
    if shard_size is not None:
        migration_ms, _ = _median_ms(
            lambda: pf.store.migrate_to_sharded_yaml(shard_size=shard_size)
        )
        backend = f"sharded-yaml-{shard_size}"

    summary_before_ms, _ = _median_ms(lambda: _summary_without_index(pf, 50))
    build_ms, status = _median_ms(lambda: pf.store.configure_ticket_index(True))
    summary_indexed_ms, _ = _median_ms(
        lambda: pf.store.indexed_ticket_summaries(
            sprint="current",
            filters={},
            offset=0,
            limit=50,
        ),
        repeats=10,
    )
    ticket_id = f"PLF-{max(1, ticket_count - 1):06d}"
    get_indexed_ms, _ = _median_ms(lambda: pf.get_ticket(ticket_id), repeats=10)
    update_ms, _ = _median_ms(
        lambda: pf.update_ticket(ticket_id, priority="critical")
    )
    get_after_update_ms, _ = _median_ms(lambda: pf.get_ticket(ticket_id), repeats=10)
    stale_read_availability = _stale_read_availability(pf)
    result = {
        "backend": backend,
        "tickets": ticket_count,
        "summary_50_without_index_ms": round(summary_before_ms, 3),
        "index_build_ms": round(build_ms, 3),
        "index_bytes": status["bytes"],
        "summary_50_indexed_ms": round(summary_indexed_ms, 3),
        "indexed_get_ms": round(get_indexed_ms, 3),
        "update_with_incremental_index_ms": round(update_ms, 3),
        "indexed_get_after_update_ms": round(get_after_update_ms, 3),
        "stale_read_availability": stale_read_availability,
    }
    if migration_ms is not None:
        result["migration_ms"] = round(migration_ms, 3)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickets", type=int, default=5000)
    parser.add_argument("--shard-size", type=int, default=100)
    args = parser.parse_args()
    ticket_count = max(1, args.tickets)
    with tempfile.TemporaryDirectory(prefix="planfile-index-benchmark-") as directory:
        root = Path(directory)
        results = [
            _measure(root / "single", ticket_count, shard_size=None),
            _measure(root / "sharded", ticket_count, shard_size=max(1, args.shard_size)),
        ]
    print(
        json.dumps(
            {
                "schema": "planfile.sqlite-index-benchmark/v1",
                "ticket_count": ticket_count,
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
