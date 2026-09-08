"""Fast read/write layer for sprint YAML files.

Problem: a busy project accumulates a 40k-line ``current.yaml``; parsing it
with pure-Python ``yaml.safe_load`` costs ~2 s per read, and *every* CLI
invocation (``planfile ticket list`` runs many times per koru cycle) plus the
dashboard pays it again.

Two layers, YAML stays the single source of truth:

1. libyaml loaders/dumpers (``CSafeLoader``/``CSafeDumper``) — ~10× faster
   parse when available.
2. A self-healing JSON mirror (``<file>.fast.json``) written next to every
   sprint YAML. It embeds the YAML's post-write ``mtime_ns``; a reader uses
   the mirror only when it still matches the YAML's current mtime, so
   external/manual YAML edits simply invalidate it. Reading the mirror is
   ~300× faster than the pure-Python parse (7 ms vs 2 s on 660 tickets).
"""

from __future__ import annotations

import json
import os
import tempfile
import warnings
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import yaml

try:  # libyaml (10x faster); graceful fallback to pure python
    from yaml import CSafeLoader as FastLoader
    from yaml import CSafeDumper as FastDumper
except ImportError:  # pragma: no cover - environment without libyaml
    from yaml import SafeLoader as FastLoader
    from yaml import SafeDumper as FastDumper

_MIRROR_SUFFIX = ".fast.json"
_MIRROR_VERSION = 1


def mirror_path(path: Path) -> Path:
    return path.with_name(path.name + _MIRROR_SUFFIX)


def _json_safe(value: Any) -> Any:
    """Return the YAML value in the exact JSON-mirror representation.

    PyYAML resolves unquoted timestamps to ``date``/``datetime`` instances.
    They are valid YAML but not JSON serializable, so one timestamp in a large
    archive used to disable its mirror permanently and force every read to
    parse the whole YAML again. Normalising at the YAML boundary also keeps a
    cache miss and a mirror hit type-compatible.
    """
    if isinstance(value, dict):
        return {_json_safe(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def load_yaml_text(text: str) -> Any:
    return _json_safe(yaml.load(text, Loader=FastLoader))


def dump_yaml(data: Any, *, allow_unicode: bool = False) -> str:
    return yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=allow_unicode,
        Dumper=FastDumper,
    )


def _stat_mtime_ns(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def write_mirror(yaml_path: Path, data: Any, *, mtime_ns: int | None = None) -> None:
    """Persist the JSON mirror for ``yaml_path`` (best-effort, never raises).

    Pass ``mtime_ns`` when the caller already knows, by construction, the
    exact mtime ``data`` corresponds to (a writer stat'ing right after its
    own ``os.replace()``, or a reader that just verified the file didn't
    change under it) — DON'T let this function re-stat independently in
    that case. An independent re-stat here reopens the same TOCTOU gap
    ``read_yaml_fast`` guards against: a concurrent writer could replace the
    file between the caller's checks and this call, and re-stating now would
    stamp ``data`` (a snapshot from before that replace) with the mtime of
    the file AFTER it — a mismatched pair every later reader would trust.
    """
    if mtime_ns is None:
        mtime_ns = _stat_mtime_ns(yaml_path)
    if mtime_ns is None:
        return
    # Writers may pass values assembled in memory rather than values returned
    # by ``load_yaml_text``.  Normalize here as the final JSON boundary too;
    # otherwise one runtime datetime disables the mirror for the whole sprint.
    payload = {
        "version": _MIRROR_VERSION,
        "yaml_mtime_ns": mtime_ns,
        "data": _json_safe(data),
    }
    try:
        _atomic_write_text(mirror_path(yaml_path), json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        # The mirror is an optimization only; a failed write must never break
        # a ticket mutation. It must remain observable, otherwise a permanent
        # full-YAML fallback looks like unexplained API latency.
        warnings.warn(
            f"planfile: JSON mirror for {yaml_path.name} not written "
            f"({type(exc).__name__}: {exc}); reads fall back to full YAML parsing",
            RuntimeWarning,
            stacklevel=2,
        )


def read_mirror(yaml_path: Path, yaml_mtime_ns: int) -> Any | None:
    """Return mirrored data when it matches the YAML's current mtime."""
    try:
        raw = mirror_path(yaml_path).read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _MIRROR_VERSION:
        return None
    if payload.get("yaml_mtime_ns") != yaml_mtime_ns:
        return None  # YAML changed (external edit) — mirror is stale
    return payload.get("data")


def read_yaml_fast(path: Path) -> Any | None:
    """Read a sprint YAML via mirror when fresh; parse + heal mirror otherwise.

    Returns None when the file is missing or unparsable.

    No reader-side lock is taken here (``Store.mutation_lock()`` only
    serializes writers against each other), so a writer's atomic
    ``os.replace()`` can land at any point during this function. That is
    safe for the raw content read below — ``os.replace`` guarantees a
    reader never observes a torn file, only the fully-old or fully-new
    version — but it is NOT safe to then cache whatever we parsed under a
    mtime fetched independently afterward: if a writer replaced the file
    while we were between our own initial stat and our read, our `data`
    reflects one point in time while a later, fresh stat reflects another,
    and the two can be stamped together as if consistent. A subsequent
    reader would then trust a stale (or, worse, a from a since-superseded)
    snapshot forever, because its mtime matches the file that replaced it.
    Guard: re-stat immediately after reading and refuse to cache (though
    still return the data — it is a valid parse of *some* real snapshot)
    when the mtime moved under us.
    """
    mtime_ns = _stat_mtime_ns(path)
    if mtime_ns is None:
        return None
    mirrored = read_mirror(path, mtime_ns)
    if mirrored is not None:
        return mirrored
    try:
        data = load_yaml_text(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if _stat_mtime_ns(path) != mtime_ns:
        return data  # raced with a concurrent writer — do not cache a mismatched pair
    write_mirror(path, data, mtime_ns=mtime_ns)
    return data


def audit_mirror(path: Path) -> dict[str, Any]:
    """Compare ``path``'s on-disk ``.fast.json`` mirror against a fresh, authoritative
    YAML parse. Self-heals (rewrites the mirror) when they disagree. Never raises.

    This is the monitoring counterpart to the race ``read_yaml_fast``/``write_mirror``
    guard against: it catches a bad mirror that was already written (e.g. by a version
    of this code before the guard existed, or by any other future bug) rather than
    relying solely on prevention. Returns
    ``{"path", "ok", "healed", "reason"}`` — ``ok`` is False when drift was found
    (whether or not it could be healed), so callers can treat that as the failure
    signal regardless of whether repair succeeded.
    """
    result: dict[str, Any] = {"path": str(path), "ok": True, "healed": False, "reason": None}
    if not path.exists():
        return result
    try:
        fresh = load_yaml_text(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        result.update(ok=False, reason=f"YAML unparsable: {exc}")
        return result
    mirror_file = mirror_path(path)
    if not mirror_file.exists():
        return result  # nothing cached yet — nothing to audit
    reason: str | None = None
    cached: Any = None
    try:
        payload = json.loads(mirror_file.read_text(encoding="utf-8"))
        cached = payload.get("data") if isinstance(payload, dict) else None
    except Exception as exc:  # noqa: BLE001
        reason = f"mirror unreadable: {exc}"
    if reason is None and cached != fresh:
        reason = "cached mirror disagrees with a fresh YAML parse"
    if reason is not None:
        result.update(ok=False, reason=reason)
        mtime_ns = _stat_mtime_ns(path)
        if mtime_ns is not None:
            write_mirror(path, fresh, mtime_ns=mtime_ns)
            result["healed"] = True
    return result


def audit_project_mirrors(base_dir: Path) -> list[dict[str, Any]]:
    """Audit every ``*.yaml`` file (and its ``.fast.json`` mirror, if any) under a
    ``.planfile/`` directory. See ``audit_mirror``."""
    return [audit_mirror(p) for p in sorted(base_dir.rglob("*.yaml"))]
