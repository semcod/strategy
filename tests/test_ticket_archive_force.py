from __future__ import annotations

from datetime import timezone, datetime, timedelta

import yaml

from planfile.core.models import Ticket
from planfile.core.store import Store


def test_forced_archive_applies_retention_but_never_moves_active_ticket(tmp_path):
    store = Store(tmp_path)
    store.init()
    config = yaml.safe_load(store._config_path.read_text())
    config["archive"] = {
        "enabled": True,
        "max_current_tickets": 100,
        "max_current_bytes": 10_000_000,
        "retain_terminal_tickets": 1,
        "retain_terminal_days": 10_000,
        "terminal_statuses": ["done", "blocked"],
    }
    store._config_path.write_text(yaml.safe_dump(config, sort_keys=False))

    old = datetime.now(timezone.utc) - timedelta(days=2)
    store.create_ticket(Ticket(id="PLF-001", name="Old done", status="done", created_at=old, updated_at=old))
    store.create_ticket(Ticket(id="PLF-002", name="Old blocked", status="blocked", created_at=old, updated_at=old))
    store.create_ticket(Ticket(id="PLF-003", name="Keep active", status="open"))

    report = store.archive_completed(force=True)

    assert report["triggered"] is True
    assert report["archived"] == 1
    assert store.get_ticket("PLF-001").sprint == f"history-{old:%Y-%m-%d}"
    assert store.get_ticket("PLF-002").sprint == "current"
    assert store.get_ticket("PLF-003").sprint == "current"
