from __future__ import annotations

from datetime import timezone, datetime, timedelta

import yaml

from planfile.core.models import Ticket
from planfile.core.store import Store


def _store(tmp_path, **archive_config) -> Store:
    store = Store(tmp_path)
    store.init()
    config = yaml.safe_load(store._config_path.read_text(encoding="utf-8"))
    config["archive"].update({
        "max_current_tickets": 5,
        "max_current_bytes": 0,
        "retain_terminal_tickets": 2,
        # Capacity-focused tests use one synthetic historical date. Daily-age
        # rotation is covered separately below.
        "retain_terminal_days": 10_000,
        **archive_config,
    })
    store._write_config(config)
    return store


def _ticket(ticket_id: str, status: str, age_days: int = 0) -> Ticket:
    timestamp = datetime(2026, 7, 20, 12, tzinfo=timezone.utc) - timedelta(minutes=age_days)
    return Ticket(
        id=ticket_id,
        name=ticket_id,
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_init_enables_bounded_automatic_archiving(tmp_path):
    store = Store(tmp_path)
    store.init()

    config = yaml.safe_load(store._config_path.read_text(encoding="utf-8"))

    assert config["archive"] == Store.DEFAULT_ARCHIVE_CONFIG


def test_large_legacy_archive_models_are_not_retained(tmp_path, monkeypatch):
    store = _store(tmp_path)
    archived = _ticket("PLF-ARCHIVED", "done")
    archived.sprint = "archive-legacy"
    store.create_ticket(archived)
    archive_file = store._sprint_file("archive-legacy")
    store.MAX_CACHEABLE_YAML_BYTES = 1

    validation_calls = {"n": 0}
    original = store._ticket_from_data

    def counting_validation(ticket_data):
        validation_calls["n"] += 1
        return original(ticket_data)

    monkeypatch.setattr(store, "_ticket_from_data", counting_validation)

    assert store._tickets_from_sprint_file(archive_file)[0].id == archived.id
    assert store._tickets_from_sprint_file(archive_file)[0].id == archived.id
    assert str(archive_file) not in store._yaml_cache
    assert str(archive_file) not in store._ticket_model_cache
    assert validation_calls["n"] == 2


def test_archives_oldest_terminal_tickets_after_current_limit(tmp_path):
    store = _store(tmp_path)
    for number in range(1, 7):
        store.create_ticket(_ticket(f"PLF-{number:03d}", "done", age_days=10 - number))

    current = store.list_tickets(sprint="current")
    archived = store.list_tickets(sprint="history-2026-07-20")

    assert [ticket.id for ticket in current] == ["PLF-005", "PLF-006"]
    assert [ticket.id for ticket in archived] == [
        "PLF-001",
        "PLF-002",
        "PLF-003",
        "PLF-004",
    ]
    assert all(ticket.sprint == "history-2026-07-20" for ticket in archived)
    assert len(store.list_tickets(sprint="all")) == 6


def test_active_tickets_are_never_archived(tmp_path):
    store = _store(tmp_path, max_current_tickets=3, retain_terminal_tickets=1)
    store.create_ticket(_ticket("PLF-001", "done", age_days=3))
    store.create_ticket(_ticket("PLF-002", "done", age_days=2))
    store.create_ticket(_ticket("PLF-003", "open", age_days=1))
    store.create_ticket(_ticket("PLF-004", "in_progress"))

    assert {ticket.id for ticket in store.list_tickets(sprint="current")} == {
        "PLF-002",
        "PLF-003",
        "PLF-004",
    }
    assert [ticket.id for ticket in store.list_tickets(sprint="history-2026-07-20")] == [
        "PLF-001"
    ]


def test_archiving_can_be_disabled_per_project(tmp_path):
    store = _store(tmp_path, enabled=False, max_current_tickets=1)
    for number in range(1, 4):
        store.create_ticket(_ticket(f"PLF-{number:03d}", "done", age_days=number))

    assert len(store.list_tickets(sprint="current")) == 3
    assert not list(store._sprints_dir.glob("history-*.yaml"))


def test_list_tickets_reuses_models_until_snapshot_changes(tmp_path, monkeypatch):
    store = _store(tmp_path, enabled=False)
    store.create_ticket(_ticket("PLF-001", "open"))
    store.create_ticket(_ticket("PLF-002", "open"))
    calls = 0
    original = store._ticket_from_data

    def counted(ticket_data):
        nonlocal calls
        calls += 1
        return original(ticket_data)

    monkeypatch.setattr(store, "_ticket_from_data", counted)

    assert len(store.list_tickets(sprint="all")) == 2
    first_pass_calls = calls
    assert first_pass_calls == 2
    assert len(store.list_tickets(sprint="all")) == 2
    assert calls == first_pass_calls

    store.update_ticket("PLF-001", name="updated")

    assert [ticket.name for ticket in store.list_tickets(sprint="all") if ticket.id == "PLF-001"] == ["updated"]
    assert calls > first_pass_calls


def test_update_triggers_archiving_and_keeps_fresh_completion_current(tmp_path):
    store = _store(tmp_path, max_current_tickets=3, retain_terminal_tickets=1)
    store.create_ticket(_ticket("PLF-001", "done", age_days=3))
    store.create_ticket(_ticket("PLF-002", "done", age_days=2))
    store.create_ticket(_ticket("PLF-003", "open", age_days=1))
    # Disable archiving briefly so update_ticket is the operation crossing the limit.
    config = yaml.safe_load(store._config_path.read_text(encoding="utf-8"))
    config["archive"]["enabled"] = False
    store._write_config(config)
    store.create_ticket(_ticket("PLF-004", "open"))
    config["archive"]["enabled"] = True
    store._write_config(config)

    updated = store.update_ticket("PLF-004", status="done")

    assert updated is not None and str(updated.status.value) == "done"
    assert store.get_ticket("PLF-004").sprint == "current"
    assert store.get_ticket("PLF-001").sprint == "history-2026-07-20"


def test_size_limit_can_trigger_archiving_below_count_limit(tmp_path):
    store = _store(
        tmp_path,
        max_current_tickets=100,
        max_current_bytes=1,
        retain_terminal_tickets=1,
    )
    store.create_ticket(_ticket("PLF-001", "done", age_days=2))
    store.create_ticket(_ticket("PLF-002", "done", age_days=1))

    assert [ticket.id for ticket in store.list_tickets(sprint="current")] == ["PLF-002"]
    assert store.get_ticket("PLF-001").sprint == "history-2026-07-20"


def test_stale_terminal_tickets_move_below_capacity_limits(tmp_path):
    store = _store(
        tmp_path,
        max_current_tickets=100,
        max_current_bytes=10_000_000,
        retain_terminal_days=1,
    )
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    today = datetime.now(timezone.utc)

    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="Yesterday",
            status="done",
            created_at=yesterday,
            updated_at=yesterday,
        )
    )
    store.create_ticket(
        Ticket(
            id="PLF-002",
            name="Today",
            status="done",
            created_at=today,
            updated_at=today,
        )
    )

    assert [ticket.id for ticket in store.list_tickets(sprint="current")] == [
        "PLF-002"
    ]
    history_name = f"history-{yesterday:%Y-%m-%d}"
    assert [ticket.id for ticket in store.list_tickets(sprint=history_name)] == [
        "PLF-001"
    ]


def test_history_is_partitioned_by_terminal_completion_day(tmp_path):
    store = _store(tmp_path, retain_terminal_days=0)
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)

    for ticket_id, timestamp in (
        ("PLF-001", two_days_ago),
        ("PLF-002", yesterday),
    ):
        store.create_ticket(
            Ticket(
                id=ticket_id,
                name=ticket_id,
                status="done",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

    assert store.get_ticket("PLF-001").sprint == f"history-{two_days_ago:%Y-%m-%d}"
    assert store.get_ticket("PLF-002").sprint == f"history-{yesterday:%Y-%m-%d}"
    assert len(store.list_tickets(sprint="all")) == 2


def test_zero_day_retention_moves_fresh_terminal_ticket_immediately(tmp_path):
    store = _store(tmp_path, retain_terminal_days=0)
    now = datetime.now(timezone.utc)

    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="Freshly done",
            status="done",
            created_at=now,
            updated_at=now,
        )
    )

    assert store.list_tickets(sprint="current") == []
    assert store.get_ticket("PLF-001").sprint == f"history-{now:%Y-%m-%d}"


def test_active_lookup_does_not_parse_history_first(tmp_path, monkeypatch):
    store = _store(tmp_path, retain_terminal_days=0)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    store.create_ticket(
        Ticket(
            id="PLF-001",
            name="Archived",
            status="done",
            created_at=yesterday,
            updated_at=yesterday,
        )
    )
    store.create_ticket(_ticket("PLF-002", "open"))
    original = store._read_yaml_cached

    def reject_history(path):
        if path.stem.startswith("history-"):
            raise AssertionError("active lookup parsed history before current")
        return original(path)

    monkeypatch.setattr(store, "_read_yaml_cached", reject_history)

    assert store.get_ticket("PLF-002").sprint == "current"
