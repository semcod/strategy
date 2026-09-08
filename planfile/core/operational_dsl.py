"""Canonical Subactor Operational DSL (SODL/1) projection for Planfile events."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import timezone, datetime
from typing import Any
from urllib.parse import quote, unquote

SCHEMA = "subactor.operational-event.v1"
PREFIX = "SODL/1"
_SENSITIVE_KEY = re.compile(r"authorization|cookie|credential|password|passwd|secret|token|api[_-]?key|private[_-]?key", re.I)
_MODES = {"observe", "dry-run", "apply"}


def _canonical_value(value: Any) -> Any:
    # JavaScript JSON.stringify emits 30 for 30.0. Pydantic commonly produces
    # integral floats (for example api_timeout_seconds), so normalize them
    # before hashing/encoding to keep Python and Node byte-identical.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _redact_string(value: str) -> str:
    value = re.sub(r"([?#&](?:access_)?token=)[^&#\s]+", r"\1[REDACTED]", value, flags=re.I)
    value = re.sub(r"(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+", r"\1[REDACTED]", value, flags=re.I)
    return re.sub(r"((?:password|passwd|secret|api[_-]?key)\s*[:=]\s*)[^\s,;&]+", r"\1[REDACTED]", value, flags=re.I)


def redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {name: redact(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    return value


def _text(value: Any, fallback: str = "-") -> str:
    if isinstance(value, datetime):
        value = value.astimezone(timezone.utc).isoformat()
    normalized = str(value if value is not None else "").strip()
    return normalized or fallback


def create_event(**input: Any) -> dict[str, Any]:
    data = redact(input.get("data") or {})
    core = {
        "schema": SCHEMA,
        "timestamp": _text(input.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        "kind": _text(input.get("kind"), "operation"),
        "source": _text(input.get("source"), "planfile"),
        "ticket_id": _text(input.get("ticket_id")),
        "actor": _text(input.get("actor"), "system"),
        "oql": _text(input.get("oql") or input.get("operation"), "observe"),
        "uri": _text(input.get("uri")),
        "mode": input.get("mode") if input.get("mode") in _MODES else "observe",
        "status": _text(input.get("status"), "recorded"),
        "correlation_id": _text(input.get("correlation_id")),
        "causation_id": _text(input.get("causation_id")),
        "replayable": input.get("replayable") is not False,
        "input_hash": _text(input.get("input_hash"), _sha256(canonical_json(data))),
        "receipt_ref": _text(input.get("receipt_ref")),
        "data": data,
    }
    event_id = _text(input.get("event_id"), f"evt_{_sha256(canonical_json(core))[:24]}")
    event_hash = _sha256(canonical_json({**core, "event_id": event_id}))
    return {**core, "event_id": event_id, "event_hash": event_hash}


_FIELDS = ("event_id", "event_hash", "timestamp", "kind", "source", "ticket_id", "actor", "oql", "uri", "mode", "status", "correlation_id", "causation_id", "input_hash", "receipt_ref")


def serialize(event_input: dict[str, Any]) -> str:
    event = create_event(**event_input)
    fields = []
    for key in _FIELDS:
        label = "id" if key == "event_id" else key
        fields.append(f"{label}={quote(_text(event[key]), safe='')}" )
    fields.append(f"replayable={'true' if event['replayable'] else 'false'}")
    payload = base64.urlsafe_b64encode(canonical_json(event["data"]).encode("utf-8")).decode("ascii").rstrip("=")
    fields.append(f"data={payload}")
    return f"{PREFIX} {' '.join(fields)}"


def parse(line: str) -> dict[str, Any]:
    raw = str(line or "").strip()
    if not raw.startswith(f"{PREFIX} "):
        raise ValueError("sodl_prefix_invalid")
    tokens = dict(part.split("=", 1) for part in raw[len(PREFIX) + 1 :].split(" "))
    required = {"id", "event_hash", "timestamp", "kind", "source", "ticket_id", "actor", "oql", "uri", "mode", "status", "data"}
    if missing := required - tokens.keys():
        raise ValueError(f"sodl_field_required:{sorted(missing)[0]}")
    try:
        padded = tokens["data"] + "=" * (-len(tokens["data"]) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("sodl_data_invalid") from exc
    event = create_event(
        event_id=unquote(tokens["id"]), timestamp=unquote(tokens["timestamp"]), kind=unquote(tokens["kind"]),
        source=unquote(tokens["source"]), ticket_id=unquote(tokens["ticket_id"]), actor=unquote(tokens["actor"]),
        oql=unquote(tokens["oql"]), uri=unquote(tokens["uri"]), mode=unquote(tokens["mode"]), status=unquote(tokens["status"]),
        correlation_id=unquote(tokens.get("correlation_id", "-")), causation_id=unquote(tokens.get("causation_id", "-")),
        input_hash=unquote(tokens.get("input_hash", "-")), receipt_ref=unquote(tokens.get("receipt_ref", "-")),
        replayable=tokens.get("replayable") != "false", data=data,
    )
    if event["event_hash"] != unquote(tokens["event_hash"]):
        raise ValueError("sodl_event_hash_invalid")
    if serialize(event) != raw:
        raise ValueError("sodl_line_not_canonical")
    return event


def line(**input: Any) -> str:
    return serialize(create_event(**input))
