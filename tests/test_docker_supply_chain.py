from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
DIGEST_FROM = re.compile(r"^FROM\s+\S+@sha256:[0-9a-f]{64}(?:\s+AS\s+\S+)?$", re.MULTILINE)


def test_every_runner_stage_uses_an_immutable_image_digest() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]

    assert from_lines
    assert all(DIGEST_FROM.fullmatch(line) for line in from_lines)


def test_runner_uses_only_frozen_python_resolution() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")

    assert "uv sync --frozen --no-dev --extra all --no-editable" in text
    assert "COPY pyproject.toml uv.lock README.md ./" in text
    assert "pip install" not in text
    assert "install.sh" not in text
    assert "curl " not in text


def test_docker_context_is_an_explicit_allowlist() -> None:
    entries = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    active = [line for line in entries if line and not line.startswith("#")]

    assert active[0] == "*"
    assert set(active[1:]) == {
        "!.dockerignore",
        "!Dockerfile",
        "!README.md",
        "!pyproject.toml",
        "!uv.lock",
        "!planfile/",
        "!planfile/**",
        "!scripts/",
        "!scripts/docker-entrypoint.sh",
    }
