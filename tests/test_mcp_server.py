"""Tests for Model Context Protocol (MCP) server integration."""

import json
import sys
from io import StringIO

import pytest

from planfile import Planfile
from planfile.mcp import server


@pytest.fixture(autouse=True)
def _allow_test_mutations(monkeypatch, tmp_path):
    monkeypatch.setenv("PLANFILE_MCP_ALLOW_MUTATION", "1")
    monkeypatch.setenv("PLANFILE_MCP_PROJECT_ROOT", str(tmp_path))


def test_mcp_handle_tool_call_list_tickets(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(
        name="MCP test ticket",
        priority="high",
        sprint="current",
    )

    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    # Test list_tickets tool
    res = server.handle_tool_call("planfile_list_tickets", {"sprint": "current"})
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["id"] == ticket.id
    assert res[0]["name"] == "MCP test ticket"


def test_mcp_handle_tool_call_create_ticket(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    res = server.handle_tool_call(
        "planfile_create_ticket",
        {
            "name": "New from MCP",
            "priority": "critical",
            "sprint": "current",
            "description": "Created via MCP tool",
            "labels": ["ai", "mcp"],
        },
    )
    assert res["name"] == "New from MCP"
    assert res["priority"] == "critical"
    assert "id" in res


def test_mcp_handle_tool_call_get_and_update_ticket(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    ticket = pf.create_ticket(name="Initial name")
    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    # Get ticket
    res_get = server.handle_tool_call("planfile_get_ticket", {"ticket_id": ticket.id})
    assert res_get["name"] == "Initial name"

    # Update ticket
    res_up = server.handle_tool_call(
        "planfile_update_ticket", {"ticket_id": ticket.id, "name": "Updated name", "priority": "high"}
    )
    assert res_up["name"] == "Updated name"
    assert res_up["priority"] == "high"


def test_mcp_yaml_get_and_patch(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    # Write dummy planfile.yaml
    pf_path = tmp_path / "planfile.yaml"
    pf_path.write_text("metadata:\n  model_tier: balanced\nsprints: []\n", encoding="utf-8")

    monkeypatch.setattr(server, "get_planfile", lambda: pf)

    # Get yaml
    res_get = server.handle_tool_call("planfile_yaml_get", {"project_path": str(tmp_path)})
    assert res_get["metadata"]["model_tier"] == "balanced"

    # Patch yaml
    res_patch = server.handle_tool_call(
        "planfile_yaml_patch",
        {
            "path": "metadata.model_tier",
            "value": "premium",
            "project_path": str(tmp_path),
        },
    )
    assert res_patch["patched"] == "metadata.model_tier"
    assert res_patch["value"] == "premium"

    # Verify write
    res_get_new = server.handle_tool_call("planfile_yaml_get", {"project_path": str(tmp_path)})
    assert res_get_new["metadata"]["model_tier"] == "premium"


def test_mcp_jsonrpc_stdio_lifecycle(monkeypatch):
    input_stream = StringIO(
        json.dumps({"method": "initialize", "id": 1, "params": {}}) + "\n" +
        json.dumps({"method": "tools/list", "id": 2, "params": {}}) + "\n"
    )
    output_stream = StringIO()

    monkeypatch.setattr(sys, "stdin", input_stream)
    monkeypatch.setattr(sys, "stdout", output_stream)

    server.main()

    lines = output_stream.getvalue().strip().split("\n")
    assert len(lines) == 2

    init_res = json.loads(lines[0])
    assert init_res["id"] == 1
    assert init_res["result"]["serverInfo"]["name"] == "planfile"

    list_res = json.loads(lines[1])
    assert list_res["id"] == 2
    assert "tools" in list_res["result"]
    assert any(t["name"] == "planfile_dsl" for t in list_res["result"]["tools"])


def test_mcp_mutations_require_operator_capability(monkeypatch, tmp_path):
    monkeypatch.delenv("PLANFILE_MCP_ALLOW_MUTATION", raising=False)

    with pytest.raises(PermissionError, match="PLANFILE_MCP_ALLOW_MUTATION"):
        server._guard_tool_call("planfile_create_ticket", {})
    with pytest.raises(PermissionError, match="PLANFILE_MCP_ALLOW_MUTATION"):
        server._guard_tool_call(
            "planfile_dsl",
            {"command": "delete ticket PLF-001", "project_path": str(tmp_path)},
        )

    server._guard_tool_call(
        "planfile_dsl",
        {"command": "list tickets", "project_path": str(tmp_path)},
    )


def test_mcp_project_path_is_confined(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("PLANFILE_MCP_PROJECT_ROOT", str(allowed))

    assert server._require_project_path(str(allowed / "project")).startswith(str(allowed))
    with pytest.raises(PermissionError, match="PLANFILE_MCP_PROJECT_ROOT"):
        server._require_project_path(str(tmp_path / "outside"))
