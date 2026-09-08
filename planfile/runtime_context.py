from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import timezone, datetime
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": {
        "systems": True,
        "libraries": True,
        "algorithms": True,
        "apis": True,
        "applications": True,
        "pipelines": True,
        "topology": True,
    },
    "overrides": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if raw.startswith("TestQL"):
        raw = raw[raw.find("{") :]
    return json.loads(raw)


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read_toml(path: Path) -> Any:
    if not path.exists():
        return None
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(path.read_text(encoding="utf-8"))
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)


def runtime_context_config_path(project: Path) -> Path:
    return project.resolve() / ".koru" / "runtime-context.json"


def load_runtime_context_config(project: Path | str = ".") -> dict[str, Any]:
    project_path = Path(project).resolve()
    path = runtime_context_config_path(project_path)
    if not path.exists():
        return {
            "enabled": dict(DEFAULT_CONFIG["enabled"]),
            "overrides": {},
        }
    data = _read_json(path)
    if not isinstance(data, dict):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged["enabled"] = {**DEFAULT_CONFIG["enabled"], **data.get("enabled", {})}
    merged["overrides"] = data.get("overrides", {}) if isinstance(data.get("overrides"), dict) else {}
    if data.get("updated_at"):
        merged["updated_at"] = data["updated_at"]
    return merged


def save_runtime_context_config(project: Path | str = ".", data: dict[str, Any] | None = None) -> dict[str, Any]:
    project_path = Path(project).resolve()
    source = data or DEFAULT_CONFIG
    normalized = dict(DEFAULT_CONFIG)
    normalized["enabled"] = {**DEFAULT_CONFIG["enabled"], **source.get("enabled", {})}
    normalized["overrides"] = source.get("overrides", {}) if isinstance(source.get("overrides"), dict) else {}
    normalized["updated_at"] = _now()
    _write_json(runtime_context_config_path(project_path), normalized)
    return normalized


def _package_summary(project: Path) -> dict[str, Any]:
    package = _read_json(project / "package.json") or {}
    discovered_packages: list[dict[str, Any]] = []
    if not package:
        for manifest in sorted(project.glob("*/package.json")):
            child = _read_json(manifest)
            if isinstance(child, dict):
                discovered_packages.append(
                    {
                        "path": str(manifest.parent.relative_to(project)),
                        "name": child.get("name", manifest.parent.name),
                        "version": child.get("version"),
                    }
                )
    dependencies = package.get("dependencies", {}) or {}
    dev_dependencies = package.get("devDependencies", {}) or {}
    return {
        "name": package.get("name", os.environ.get("PLANFILE_RUNTIME_CONTEXT_PROJECT_NAME", project.name)),
        "version": package.get("version"),
        "description": package.get("description"),
        "workspaces": package.get("workspaces", []) or [item["path"] for item in discovered_packages],
        "packages": discovered_packages,
        "scripts": package.get("scripts", {}),
        "dependencies": dependencies,
        "devDependencies": dev_dependencies,
    }


def _pyproject_summary(project: Path) -> dict[str, Any]:
    pyproject = _read_toml(project / "pyproject.toml") or {}
    project_meta = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    return {
        "name": project_meta.get("name", project.name),
        "version": project_meta.get("version"),
        "description": project_meta.get("description"),
        "dependencies": project_meta.get("dependencies", []) or [],
        "optionalDependencies": project_meta.get("optional-dependencies", {}) or {},
    }


def _compose_paths(project: Path) -> list[Path]:
    names = [
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.hardware.yml",
        "docker-compose.observability.yml",
        "docker-compose.quality.yml",
        "docker-compose.prod.yml",
    ]
    paths = [project / name for name in names]
    for directory in sorted(path for path in project.iterdir() if path.is_dir()):
        paths.extend(directory / name for name in names)
    return paths


def _compose_services(project: Path) -> list[dict[str, Any]]:
    services: dict[str, dict[str, Any]] = {}
    for path in _compose_paths(project):
        compose = _read_yaml(path)
        if not compose or not isinstance(compose.get("services"), dict):
            continue
        for name, spec in compose["services"].items():
            item = services.setdefault(
                name,
                {
                    "name": name,
                    "compose_files": [],
                    "ports": [],
                    "environment": {},
                    "depends_on": [],
                    "image": None,
                    "build": None,
                },
            )
            item["compose_files"].append(str(path.relative_to(project)))
            item["image"] = spec.get("image") or item.get("image")
            item["build"] = spec.get("build") or item.get("build")
            item["ports"] = item["ports"] or spec.get("ports", []) or []
            env = spec.get("environment", {}) or {}
            if isinstance(env, list):
                for entry in env:
                    if isinstance(entry, str):
                        key = entry.split("=", 1)[0]
                        item["environment"][key] = "<redacted>"
            elif isinstance(env, dict):
                item["environment"].update({str(key): "<redacted>" for key in env})
            depends = spec.get("depends_on", []) or []
            if isinstance(depends, dict):
                depends = list(depends.keys())
            item["depends_on"] = sorted(set(item["depends_on"] + list(depends)))
    return sorted(services.values(), key=lambda service: service["name"])


def _task_pipelines(project: Path) -> list[dict[str, Any]]:
    taskfile = _read_yaml(project / "Taskfile.yml")
    tasks = (taskfile or {}).get("tasks", {}) if isinstance(taskfile, dict) else {}
    pipelines = []
    tokens = ("koru", "test", "deploy", "quality", "pipeline", "autoloop", "dev", "gate")
    for name, spec in sorted(tasks.items()):
        if not isinstance(spec, dict):
            continue
        if not any(token in name for token in tokens):
            continue
        pipelines.append({"name": name, "description": spec.get("desc", ""), "interactive": bool(spec.get("interactive", False))})
    return pipelines


def _topology_summary(project: Path) -> dict[str, Any]:
    topology_path = project / ".testql" / "topology.json"
    topology = _read_json(topology_path) or {}
    nodes = topology.get("nodes", []) if isinstance(topology, dict) else []
    edges = topology.get("edges", []) if isinstance(topology, dict) else []
    traces = topology.get("traces", []) if isinstance(topology, dict) else []
    return {
        "path": str(topology_path.relative_to(project)) if topology_path.exists() else None,
        "confidence": topology.get("confidence") if isinstance(topology, dict) else None,
        "metadata": topology.get("metadata", {}) if isinstance(topology, dict) else {},
        "node_count": len(nodes),
        "edge_count": len(edges),
        "trace_count": len(traces),
        "nodes": nodes[:100],
        "edges": edges[:100],
        "traces": traces[:50],
    }


def build_runtime_context(
    project: Path | str = ".",
    *,
    config_project: Path | str | None = None,
) -> dict[str, Any]:
    project_path = Path(project).resolve()
    config_path = Path(config_project).resolve() if config_project is not None else project_path
    config = load_runtime_context_config(config_path)
    package = _package_summary(project_path)
    pyproject = _pyproject_summary(project_path)
    services = _compose_services(project_path)
    pipelines = _task_pipelines(project_path)
    topology = _topology_summary(project_path)
    planfile_config = _read_yaml(project_path / ".planfile" / "config.yaml") or {}
    enabled = config.get("enabled", {})
    project_name = package.get("name") or pyproject.get("name") or project_path.name
    project_version = package.get("version") or pyproject.get("version")
    return {
        "generated_at": _now(),
        "project_root": str(project_path),
        "config": config,
        "summary": {
            "project": project_name,
            "version": project_version,
            "services": len(services),
            "workspaces": len(package.get("workspaces", [])),
            "pipelines": len(pipelines),
            "topology_nodes": topology.get("node_count", 0),
        },
        "systems": services if enabled.get("systems", True) else [],
        "libraries": {
            "node": package,
            "python": pyproject,
        } if enabled.get("libraries", True) else {},
        "algorithms": [
            {"name": "Koru autonomous ticket loop", "role": "agent orchestration", "source": "Taskfile.yml / .koru"},
            {"name": "Planfile", "role": "ticket and sprint state", "source": ".planfile"},
            {"name": "TestQL topology discovery", "role": "runtime topology evidence graph", "source": ".testql/topology.json"},
        ] if enabled.get("algorithms", True) else [],
        "apis": [
            {"name": "planfile REST", "base_url": "http://localhost:8765", "endpoints": ["/tickets", "/health"]},
            {"name": "runtime context", "base_url": "http://localhost:8765", "endpoints": ["/runtime-context", "/api/runtime-context", "/api/runtime-context/config"]},
        ] if enabled.get("apis", True) else [],
        "applications": [
            {"name": "Planfile/Koru dashboard", "url": "http://localhost:8765/", "role": "operator control plane"},
            {"name": "Runtime Context", "url": "http://localhost:8765/runtime-context", "role": "topology and pipeline visibility"},
        ] if enabled.get("applications", True) else [],
        "pipelines": pipelines if enabled.get("pipelines", True) else [],
        "topology": topology if enabled.get("topology", True) else {},
        "planfile": planfile_config,
    }
