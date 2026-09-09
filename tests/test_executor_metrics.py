"""Regression coverage for optional context metrics and diagnostic failures."""

import logging
from pathlib import Path

import pytest

from planfile.core.models import Task
from planfile.executor_standalone import StrategyExecutor


def test_invalid_encoding_keeps_valid_metrics_and_reports_partial(tmp_path, caplog):
    (tmp_path / "valid.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "invalid.py").write_bytes(b"\xffprivate-source")
    with caplog.at_level(logging.WARNING):
        result = StrategyExecutor()._get_project_metrics(tmp_path)
    assert result["total_lines"] == 1
    assert result["total_files"] == 2
    assert result["files_failed"] == 1
    assert result["complete"] is False
    assert "PLANFILE_METRICS_FILE_READ_FAILED" in caplog.text
    assert "UnicodeDecodeError" in caplog.text
    assert "private-source" not in caplog.text
    assert str(tmp_path) not in caplog.text


def test_permission_error_is_observable_without_exception_payload(tmp_path, monkeypatch, caplog):
    (tmp_path / "denied.py").touch()

    def denied(*args, **kwargs):
        raise PermissionError("private-path-and-credential")

    monkeypatch.setattr(Path, "read_text", denied)
    with caplog.at_level(logging.WARNING):
        result = StrategyExecutor()._get_project_metrics(tmp_path)
    assert result["complete"] is False
    assert result["files_failed"] == 1
    assert "PermissionError" in caplog.text
    assert "private-path-and-credential" not in caplog.text


def test_enumeration_failure_keeps_optional_fallback_with_diagnostic(monkeypatch, caplog):
    def denied(*args, **kwargs):
        raise OSError("private-directory")

    monkeypatch.setattr(Path, "rglob", denied)
    with caplog.at_level(logging.WARNING):
        assert StrategyExecutor()._get_project_metrics(".") is None
    assert "PLANFILE_METRICS_UNAVAILABLE" in caplog.text
    assert "private-directory" not in caplog.text


def test_programming_error_is_not_silently_converted_to_metrics(tmp_path, monkeypatch):
    (tmp_path / "source.py").touch()

    def broken(*args, **kwargs):
        raise RuntimeError("unexpected implementation bug")

    monkeypatch.setattr(Path, "read_text", broken)
    with pytest.raises(RuntimeError, match="implementation bug"):
        StrategyExecutor()._get_project_metrics(tmp_path)


def test_readable_project_is_complete(tmp_path, caplog):
    (tmp_path / "source.py").write_text("x = 1\n", encoding="utf-8")
    result = StrategyExecutor()._get_project_metrics(tmp_path)
    assert result["complete"] is True
    assert result["files_failed"] == 0
    assert not caplog.records


def test_llm_prompt_marks_partial_file_read_coverage(tmp_path):
    (tmp_path / "invalid.py").write_bytes(b"\xff")
    prompt = StrategyExecutor()._build_prompt(
        Task(name="review", description="Review the project"), tmp_path
    )
    assert "File-read coverage complete: False" in prompt
    assert "Files omitted due to read errors: 1" in prompt
