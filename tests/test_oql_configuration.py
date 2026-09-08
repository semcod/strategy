from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from planfile import Planfile
from planfile.api import server
from planfile.cli.commands import app
from planfile.dsl import DSLExecutor, DSLParser
from planfile.integrations.config import IntegrationConfig
from planfile.mcp.server import handle_tool_call


def _executor(tmp_path: Path) -> DSLExecutor:
    return DSLExecutor(str(tmp_path))


def test_parser_recognizes_configuration_objects_and_dotted_paths():
    parser = DSLParser()

    listed = parser.parse("list settings")
    changed = parser.parse(
        "set config store.archive.enabled=false "
        "store.archive.max_current_tickets=250"
    )

    assert listed.object_type == "config"
    assert changed.verb == "update"
    assert changed.object_type == "config"
    assert changed.params == {
        "store.archive.enabled": False,
        "store.archive.max_current_tickets": 250,
    }


def test_list_and_show_config_expose_contract_and_redact_integrations(tmp_path):
    (tmp_path / "github.planfile.yaml").write_text(
        yaml.safe_dump(
            {
                "integrations": {
                    "github": {
                        "repo": "owner/project",
                        "token": "should-never-be-returned",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    executor = _executor(tmp_path)

    listed = executor.run("list config")
    shown = executor.run("show config integrations.github.token")
    excluded = executor.run("show config store.next_id")

    assert listed.ok
    assert listed.data["values"]["integrations"]["github"]["token"] == "[REDACTED]"
    assert "store.storage.backend" in listed.data["writable"]
    assert shown.ok
    assert shown.data["value"] == "[REDACTED]"
    assert shown.data["writable"] is False
    assert excluded.ok
    assert excluded.data["value"] is None
    assert excluded.data["writable"] is False


def test_set_store_config_is_atomic_and_records_oql_event(tmp_path):
    executor = _executor(tmp_path)

    result = executor.run(
        "set config store.archive.enabled=false "
        "store.archive.max_current_tickets=250 "
        "store.archive.terminal_statuses=done,failed "
        'reason="large project"'
    )

    assert result.ok, result.error
    config = yaml.safe_load((tmp_path / ".planfile" / "config.yaml").read_text())
    assert config["archive"]["enabled"] is False
    assert config["archive"]["max_current_tickets"] == 250
    assert config["archive"]["terminal_statuses"] == ["done", "failed"]
    event = Planfile(str(tmp_path)).store.operational_events(limit=1)[0]["event"]
    assert event["oql"] == "config.set"
    assert event["kind"] == "configuration"
    assert event["data"]["reason"] == "large project"


def test_dry_run_validates_without_writing(tmp_path):
    executor = _executor(tmp_path)
    config_path = tmp_path / ".planfile" / "config.yaml"
    executor.run("list config")
    before = config_path.read_bytes()

    result = executor.run(
        "set config store.archive.max_current_tickets=500 mode=dry-run"
    )

    assert result.ok
    assert result.data["mode"] == "dry-run"
    assert result.data["changed"][0]["new"] == 500
    assert config_path.read_bytes() == before
    assert not (tmp_path / ".planfile" / "events" / "operations.jsonl").exists()


def test_invalid_batch_does_not_partially_write(tmp_path):
    executor = _executor(tmp_path)
    executor.run("list config")
    config_path = tmp_path / ".planfile" / "config.yaml"
    before = config_path.read_bytes()

    result = executor.run(
        "set config store.archive.enabled=false store.next_id=1"
    )

    assert not result.ok
    assert result.error == "config_path_allocator_owned"
    assert config_path.read_bytes() == before


def test_runtime_config_and_nested_override_are_persisted(tmp_path):
    executor = _executor(tmp_path)

    result = executor.run(
        "set config runtime.enabled.systems=false "
        "runtime.overrides.discovery.max_depth=4"
    )

    assert result.ok, result.error
    runtime = json.loads(
        (tmp_path / ".koru" / "runtime-context.json").read_text(encoding="utf-8")
    )
    assert runtime["enabled"]["systems"] is False
    assert runtime["overrides"]["discovery"]["max_depth"] == 4
    shown = executor.run("show config runtime.overrides.discovery.max_depth")
    assert shown.ok
    assert shown.data["value"] == 4


def test_sensitive_runtime_override_and_mixed_scope_are_rejected(tmp_path):
    executor = _executor(tmp_path)

    sensitive = executor.run("set config runtime.overrides.github.token=unsafe")
    mixed = executor.run(
        "set config store.archive.enabled=false runtime.enabled.systems=false"
    )

    assert not sensitive.ok
    assert sensitive.error == "config_sensitive_path_forbidden"
    assert not mixed.ok
    assert mixed.error == "config_mixed_scope_not_atomic"
    assert not (tmp_path / ".koru" / "runtime-context.json").exists()


def test_oql_index_transition_builds_and_disables_sqlite_index(tmp_path):
    pf = Planfile(str(tmp_path))
    pf.create_ticket("Indexed")
    executor = _executor(tmp_path)

    enabled = executor.run("set config store.storage.index=sqlite")

    assert enabled.ok, enabled.error
    assert enabled.data["operation"]["enabled"] is True
    assert enabled.data["operation"]["tickets"] == 1
    assert (tmp_path / ".planfile" / "index" / "tickets.sqlite3").exists()
    disabled = executor.run("set config store.storage.index=none")
    assert disabled.ok, disabled.error
    assert disabled.data["operation"]["enabled"] is False


def test_oql_backend_transition_runs_verified_migration(tmp_path):
    pf = Planfile(str(tmp_path))
    first = pf.create_ticket("First")
    second = pf.create_ticket("Second")
    executor = _executor(tmp_path)

    result = executor.run(
        "set config store.storage.backend=sharded-yaml "
        "store.storage.shard_size=1 store.storage.custom_shards=8"
    )

    assert result.ok, result.error
    assert result.data["operation"]["backend"] == "sharded-yaml"
    assert result.data["operation"]["tickets"] == 2
    assert Path(result.data["operation"]["backup_dir"]).exists()
    reloaded = Planfile(str(tmp_path))
    assert reloaded.store.storage_backend() == "sharded-yaml"
    assert reloaded.get_ticket(first.id).name == "First"
    assert reloaded.get_ticket(second.id).name == "Second"

    rejected = executor.run("set config store.storage.shard_size=100")
    assert not rejected.ok
    assert rejected.error == "config_storage_reshard_required"


def test_mcp_dsl_uses_the_same_configuration_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("PLANFILE_MCP_ALLOW_MUTATION", "1")
    monkeypatch.setenv("PLANFILE_MCP_PROJECT_ROOT", str(tmp_path))
    result = handle_tool_call(
        "planfile_dsl",
        {
            "project_path": str(tmp_path),
            "command": "set config store.archive.max_current_tickets=321",
        },
    )

    assert result["ok"] is True
    config = yaml.safe_load((tmp_path / ".planfile" / "config.yaml").read_text())
    assert config["archive"]["max_current_tickets"] == 321


def test_config_cli_uses_typed_values_and_dry_run(tmp_path):
    runner = CliRunner()

    preview = runner.invoke(
        app,
        [
            "config",
            "set",
            "store.archive.enabled",
            "false",
            "--project",
            str(tmp_path),
            "--dry-run",
            "--json",
        ],
    )
    applied = runner.invoke(
        app,
        [
            "config",
            "set",
            "store.archive.enabled",
            "false",
            "--project",
            str(tmp_path),
            "--json",
        ],
    )

    assert preview.exit_code == 0
    assert json.loads(preview.output)["mode"] == "dry-run"
    assert applied.exit_code == 0
    config = yaml.safe_load((tmp_path / ".planfile" / "config.yaml").read_text())
    assert config["archive"]["enabled"] is False


def test_configuration_rest_api_uses_shared_validation(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    changed = client.patch(
        "/api/config",
        json={
            "changes": {"store.archive.retain_terminal_tickets": 7},
            "actor": "api-test",
        },
    )
    forbidden = client.patch(
        "/api/config",
        json={"changes": {"store.next_id": 1}},
    )
    secret = client.patch(
        "/api/config",
        json={
            "changes": {
                "runtime.overrides": {"provider": {"api_key": "unsafe"}}
            }
        },
    )
    shown = client.get("/api/config/value/store.archive.retain_terminal_tickets")

    assert changed.status_code == 200
    assert changed.json()["changed"][0]["new"] == 7
    assert forbidden.status_code == 400
    assert forbidden.json()["detail"] == "config_path_allocator_owned"
    assert secret.status_code == 400
    assert secret.json()["detail"].startswith("config_sensitive_path_forbidden")
    assert shown.status_code == 200
    assert shown.json()["value"] == 7


def test_configuration_revision_is_stable_for_ticket_allocation_and_changes_on_config(
    tmp_path,
):
    pf = Planfile(str(tmp_path))
    first = pf.configuration.revision()

    pf.create_ticket("Allocation is not configuration")
    after_ticket = pf.configuration.revision()
    changed = pf.configuration.set_many(
        {"store.archive.max_current_tickets": 432},
        expected_revision=after_ticket,
    )

    assert after_ticket == first
    assert changed["previous_revision"] == first
    assert changed["revision"] != first
    assert pf.configuration.revision() == changed["revision"]


def test_stale_revision_rejects_oql_without_partial_write(tmp_path):
    executor = _executor(tmp_path)
    original = executor.run("list config").data["revision"]
    first = executor.run(
        f"set config store.archive.enabled=false if_revision={original}"
    )
    config_path = tmp_path / ".planfile" / "config.yaml"
    before_stale_write = config_path.read_bytes()

    stale = executor.run(
        f"set config store.archive.max_current_tickets=999 if_revision={original}"
    )

    assert first.ok
    assert not stale.ok
    assert stale.error.startswith("config_revision_conflict:")
    assert config_path.read_bytes() == before_stale_write


def test_rest_etag_supports_optimistic_configuration_writes(tmp_path, monkeypatch):
    pf = Planfile(str(tmp_path))
    monkeypatch.setattr(server, "get_planfile", lambda: pf)
    client = TestClient(server.app)

    listed = client.get("/api/config")
    etag = listed.headers["etag"]
    applied = client.patch(
        "/api/config",
        headers={"If-Match": etag},
        json={"changes": {"store.archive.retain_terminal_tickets": 9}},
    )
    stale = client.patch(
        "/api/config",
        headers={"If-Match": etag},
        json={"changes": {"store.archive.retain_terminal_tickets": 10}},
    )

    assert etag == f'"{listed.json()["revision"]}"'
    assert applied.status_code == 200
    assert applied.headers["etag"] == f'"{applied.json()["revision"]}"'
    assert applied.headers["etag"] != etag
    assert stale.status_code == 409
    assert stale.json()["detail"].startswith("config_revision_conflict:")
    assert pf.configuration.show("store.archive.retain_terminal_tickets")["value"] == 9


def test_integration_oql_uses_canonical_overlay_without_rewriting_source(tmp_path):
    source_path = tmp_path / "github.planfile.yaml"
    source_path.write_text(
        "# keep this comment\n"
        "integrations:\n"
        "  github:\n"
        "    repo: old/project\n"
        "    token: ${GITHUB_TOKEN}\n",
        encoding="utf-8",
    )
    original_source = source_path.read_bytes()
    executor = _executor(tmp_path)

    result = executor.run(
        "set config integrations.github.repo=new/project "
        "integrations.github.sync.create_issues=false"
    )

    assert result.ok, result.error
    assert source_path.read_bytes() == original_source
    overlay = yaml.safe_load(
        (
            tmp_path / ".planfile" / "integrations.oql.planfile.yaml"
        ).read_text(encoding="utf-8")
    )
    assert overlay["integrations"]["github"]["repo"] == "new/project"
    assert overlay["integrations"]["github"]["sync"]["create_issues"] is False
    assert result.data["operation"]["shadowed"] == [
        {
            "path": "integrations.github.repo",
            "source": "github.planfile.yaml",
        }
    ]
    effective = IntegrationConfig(str(tmp_path)).load_configs()
    assert effective["integrations"]["github"]["repo"] == "new/project"
    assert effective["integrations"]["github"]["token"] != "[REDACTED]"
    listed = executor.run("list config").data
    assert listed["values"]["integrations"]["github"]["token"] == "[REDACTED]"


def test_integration_oql_validates_allowlist_and_never_accepts_credentials(tmp_path):
    executor = _executor(tmp_path)

    token = executor.run("set config integrations.github.token=unsafe")
    username = executor.run("set config integrations.onedev.username=operator")
    invalid_url = executor.run("set config integrations.gitlab.url=not-a-url")

    assert not token.ok
    assert token.error == "config_sensitive_path_forbidden"
    assert not username.ok
    assert username.error == "config_integration_path_not_writable"
    assert not invalid_url.ok
    assert invalid_url.error == "config_value_http_url_required"
    assert not (
        tmp_path / ".planfile" / "integrations.oql.planfile.yaml"
    ).exists()


def test_config_cli_can_require_revision(tmp_path):
    pf = Planfile(str(tmp_path))
    revision = pf.configuration.revision()
    runner = CliRunner()

    applied = runner.invoke(
        app,
        [
            "config",
            "set",
            "integrations.markdown.todo_file",
            "WORK.md",
            "--project",
            str(tmp_path),
            "--if-revision",
            revision,
            "--json",
        ],
    )
    stale = runner.invoke(
        app,
        [
            "config",
            "set",
            "integrations.markdown.todo_file",
            "OTHER.md",
            "--project",
            str(tmp_path),
            "--if-revision",
            revision,
        ],
    )

    assert applied.exit_code == 0
    assert json.loads(applied.output)["previous_revision"] == revision
    assert stale.exit_code == 1
    assert "config_revision_conflict:" in stale.output
