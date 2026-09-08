"""The JSON mirror must survive YAML timestamps.

YAML resolves an unquoted ``2026-07-23 22:55:58.543703+00:00`` into a
``datetime``. ``write_mirror`` then raised ``TypeError`` inside a catch-all,
so the mirror for subactor's 21.6 MB archive was never written — silently, for
days. Every read re-parsed the whole file (~3.5 s), which is what made ticket
writes take 5-7 s instead of ~0.4 s.
"""

import json
from datetime import timezone, date, datetime

import pytest

from planfile.core.fastio import load_yaml_text, mirror_path, read_yaml_fast, write_mirror

SPRINT_YAML = """\
sprint:
  id: archive-2026-07
  tickets:
    PLF-1231:
      id: PLF-1231
      name: Zakonczone zadanie
      execution:
        finished_at: 2026-07-23 22:55:58.543703+00:00
      created_at: 2026-07-20
"""


@pytest.fixture()
def sprint_file(tmp_path):
    path = tmp_path / "archive-2026-07.yaml"
    path.write_text(SPRINT_YAML, encoding="utf-8")
    return path


def test_timestamps_parse_to_json_safe_values():
    data = load_yaml_text(SPRINT_YAML)
    ticket = data["sprint"]["tickets"]["PLF-1231"]
    assert ticket["execution"]["finished_at"] == "2026-07-23T22:55:58.543703+00:00"
    assert ticket["created_at"] == "2026-07-20"
    json.dumps(data)  # must not raise


def test_mirror_is_written_for_a_file_containing_timestamps(sprint_file):
    read_yaml_fast(sprint_file)
    mirror = mirror_path(sprint_file)
    assert mirror.exists(), "mirror was not written — reads will re-parse the YAML forever"
    payload = json.loads(mirror.read_text(encoding="utf-8"))
    assert payload["yaml_mtime_ns"] == sprint_file.stat().st_mtime_ns


def test_direct_writer_normalizes_runtime_timestamps(sprint_file):
    write_mirror(
        sprint_file,
        {
            "created_at": date(2026, 8, 26),
            "execution": {"finished_at": datetime(2026, 8, 26, 15, tzinfo=timezone.utc)},
        },
    )

    payload = json.loads(mirror_path(sprint_file).read_text(encoding="utf-8"))
    assert payload["data"] == {
        "created_at": "2026-08-26",
        "execution": {"finished_at": "2026-08-26T15:00:00+00:00"},
    }


def test_second_read_is_served_from_the_mirror(sprint_file):
    first = read_yaml_fast(sprint_file)

    # Corrupt the YAML: a mirror hit must not touch it. If the mirror were
    # missing or stale, this read would fail to parse and return None.
    sprint_file.write_text(SPRINT_YAML, encoding="utf-8")
    import os

    stat = sprint_file.stat()
    os.utime(sprint_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    read_yaml_fast(sprint_file)

    mirror = mirror_path(sprint_file)
    payload = json.loads(mirror.read_text(encoding="utf-8"))
    assert payload["data"] == first


def test_mirror_write_failure_is_reported_not_swallowed(sprint_file, monkeypatch):
    from planfile.core import fastio

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(fastio, "_atomic_write_text", boom)
    with pytest.warns(RuntimeWarning, match="mirror"):
        assert read_yaml_fast(sprint_file) is not None
