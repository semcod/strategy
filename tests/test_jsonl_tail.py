"""Bounded newest-first JSONL reads must match the forward reader they replace."""

from __future__ import annotations

import json
import random
from collections import deque
from pathlib import Path

import pytest

from planfile.core.jsonl_tail import read_jsonl_tail


def forward_reference(path: Path, *, limit: int, ticket_id: str | None = None) -> list[dict]:
    """The original full-file implementation, kept as the oracle."""
    bounded: deque[dict] = deque(maxlen=max(1, min(int(limit), 5000)))
    try:
        source = path.open("r", encoding="utf-8")
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


def keep_ticket(ticket_id: str):
    return lambda row: str((row.get("event") or {}).get("ticket_id") or "") == str(ticket_id)


def write_rows(path: Path, rows: list[dict], *, trailing_newline: bool = True) -> None:
    body = "\n".join(json.dumps(row) for row in rows)
    path.write_text(body + ("\n" if trailing_newline else ""), encoding="utf-8")


def journal(index: int, ticket: str = "PLF-1") -> dict:
    return {"seq": index, "event": {"ticket_id": ticket, "oql": "ticket.update"}}


def test_missing_file_is_an_empty_result(tmp_path):
    assert read_jsonl_tail(tmp_path / "absent.jsonl", limit=10) == []


def test_empty_file_is_an_empty_result(tmp_path):
    path = tmp_path / "operations.jsonl"
    path.write_text("", encoding="utf-8")
    assert read_jsonl_tail(path, limit=10) == []


def test_rows_come_back_newest_first(tmp_path):
    path = tmp_path / "operations.jsonl"
    write_rows(path, [journal(i) for i in range(5)])
    assert [row["seq"] for row in read_jsonl_tail(path, limit=10)] == [4, 3, 2, 1, 0]


def test_limit_takes_the_newest_rows(tmp_path):
    path = tmp_path / "operations.jsonl"
    write_rows(path, [journal(i) for i in range(100)])
    assert [row["seq"] for row in read_jsonl_tail(path, limit=3)] == [99, 98, 97]


def test_a_file_without_a_trailing_newline_keeps_its_last_row(tmp_path):
    path = tmp_path / "operations.jsonl"
    write_rows(path, [journal(i) for i in range(4)], trailing_newline=False)
    assert [row["seq"] for row in read_jsonl_tail(path, limit=2)] == [3, 2]


def test_blank_and_malformed_lines_are_skipped(tmp_path):
    path = tmp_path / "operations.jsonl"
    path.write_text(
        "\n".join([
            json.dumps(journal(0)),
            "",
            "{not json",
            "   ",
            json.dumps(journal(1)),
            "[1, 2, 3]",
        ]) + "\n",
        encoding="utf-8",
    )
    assert [row["seq"] for row in read_jsonl_tail(path, limit=10)] == [1, 0]


def test_a_filter_selects_only_matching_rows(tmp_path):
    path = tmp_path / "operations.jsonl"
    rows = [journal(i, "PLF-1" if i % 2 == 0 else "PLF-2") for i in range(20)]
    write_rows(path, rows)
    got = read_jsonl_tail(path, limit=3, keep=keep_ticket("PLF-2"))
    assert [row["seq"] for row in got] == [19, 17, 15]


def test_rows_spanning_chunk_boundaries_are_not_split(tmp_path):
    path = tmp_path / "operations.jsonl"
    rows = [{"seq": i, "pad": "x" * 300, "event": {"ticket_id": "PLF-1"}} for i in range(200)]
    write_rows(path, rows)
    # A chunk far smaller than one row forces every boundary case.
    got = read_jsonl_tail(path, limit=200, chunk_bytes=1024, max_bytes=1 << 30)
    assert [row["seq"] for row in got] == list(reversed(range(200)))


def test_a_single_row_longer_than_a_chunk_is_recovered(tmp_path):
    path = tmp_path / "operations.jsonl"
    write_rows(path, [{"seq": 0, "pad": "y" * 20000, "event": {"ticket_id": "PLF-1"}}])
    got = read_jsonl_tail(path, limit=5, chunk_bytes=1024, max_bytes=1 << 30)
    assert [row["seq"] for row in got] == [0]


def test_the_byte_budget_stops_a_sparse_filter_early(tmp_path):
    path = tmp_path / "operations.jsonl"
    # The only match sits at the head, far outside the budget.
    rows = [journal(0, "PLF-OLD")] + [journal(i, "PLF-NEW") for i in range(1, 500)]
    write_rows(path, rows)
    assert read_jsonl_tail(path, limit=5, keep=keep_ticket("PLF-OLD"), max_bytes=1024) == []
    # With room to walk the whole file, the same query finds it.
    found = read_jsonl_tail(path, limit=5, keep=keep_ticket("PLF-OLD"), max_bytes=1 << 30)
    assert [row["seq"] for row in found] == [0]


def test_the_budget_never_truncates_an_unfiltered_tail_read(tmp_path):
    path = tmp_path / "operations.jsonl"
    write_rows(path, [journal(i) for i in range(2000)])
    got = read_jsonl_tail(path, limit=200, max_bytes=64 * 1024)
    assert len(got) == 200
    assert got[0]["seq"] == 1999


@pytest.mark.parametrize("seed", range(12))
def test_it_agrees_with_the_forward_reader_on_random_journals(tmp_path, seed):
    rng = random.Random(seed)
    path = tmp_path / "operations.jsonl"
    lines: list[str] = []
    for index in range(rng.randint(0, 400)):
        roll = rng.random()
        if roll < 0.05:
            lines.append("")
        elif roll < 0.10:
            lines.append("{ broken")
        else:
            ticket = rng.choice(["PLF-1", "PLF-2", "PLF-3"])
            pad = "z" * rng.randint(0, 400)
            lines.append(json.dumps({"seq": index, "pad": pad, "event": {"ticket_id": ticket}}))
    body = "\n".join(lines)
    path.write_text(body + ("\n" if rng.random() < 0.8 else ""), encoding="utf-8")

    limit = rng.randint(1, 50)
    for ticket_id in (None, "PLF-2"):
        expected = forward_reference(path, limit=limit, ticket_id=ticket_id)
        got = read_jsonl_tail(
            path,
            limit=limit,
            keep=None if ticket_id is None else keep_ticket(ticket_id),
            max_bytes=1 << 30,
            chunk_bytes=rng.choice([1024, 4096, 1 << 20]),
        )
        assert got == expected, f"seed={seed} ticket={ticket_id} limit={limit}"
