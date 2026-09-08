"""Bounded newest-first reads of append-only JSONL journals.

An append-only journal is written at its end and read from its end, so a reader
that starts at byte zero pays for the entire history to answer a question about
the last few hundred rows. This walks backwards in chunks and stops as soon as
it has enough, with a byte budget so a filter that matches nothing recent cannot
turn into a full scan.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

#: Default reverse-walk budget.
#:
#: An unfiltered read fills its limit from the last few kilobytes, so the budget
#: only ever matters to a filtered query, where it decides how far back that
#: filter may search. 256 MiB covers well over the recent history of the largest
#: observed journal (379 MB) while still turning the unbounded worst case into a
#: bounded one. A filtered query returns the matches inside this window, newest
#: first; it is not a promise of every match in history.
OPERATIONS_TAIL_MAX_BYTES = 256 * 1024 * 1024

_CHUNK_BYTES = 1024 * 1024


def _parse(raw: bytes) -> dict | None:
    if not raw.strip():
        return None
    try:
        row = json.loads(raw)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


def read_jsonl_tail(
    path: Path,
    *,
    limit: int,
    keep: Callable[[dict], bool] | None = None,
    max_bytes: int = OPERATIONS_TAIL_MAX_BYTES,
    chunk_bytes: int = _CHUNK_BYTES,
) -> list[dict]:
    """Return up to ``limit`` matching rows, newest first.

    Blank and malformed lines are skipped, matching the forward reader this
    replaces. A missing file is an empty result, not an error.
    """
    wanted = max(1, int(limit))
    budget = max(1, int(max_bytes))
    step = max(1024, int(chunk_bytes))
    rows: list[dict] = []
    try:
        handle = path.open("rb")
    except (FileNotFoundError, NotADirectoryError):
        return []
    with handle:
        handle.seek(0, 2)
        position = handle.tell()
        carry = b""
        scanned = 0
        while position > 0 and len(rows) < wanted and scanned < budget:
            # Clamp the chunk to what is left of the budget, so a small budget
            # really is a small read rather than one oversized first chunk.
            reach = min(step, budget - scanned)
            start = max(0, position - reach)
            handle.seek(start)
            block = handle.read(position - start)
            scanned += len(block)
            buffer = block + carry
            if start == 0:
                # The head of the file is a complete line by definition.
                segments = buffer.split(b"\n")
                carry = b""
            else:
                boundary = buffer.find(b"\n")
                if boundary < 0:
                    # No line ended inside this chunk; carry it further back.
                    carry = buffer
                    position = start
                    continue
                carry = buffer[:boundary]
                segments = buffer[boundary + 1 :].split(b"\n")
            for raw in reversed(segments):
                if len(rows) >= wanted:
                    break
                row = _parse(raw)
                if row is None:
                    continue
                if keep is not None and not keep(row):
                    continue
                rows.append(row)
            position = start
    return rows
