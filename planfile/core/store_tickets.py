from __future__ import annotations

import fnmatch
import logging
from typing import Any

from .models import Ticket

logger = logging.getLogger("planfile.store")


class TicketStoreMixin:
    def _ticket_from_data(self, t_data: dict[str, Any]) -> Ticket | None:
        try:
            if 'id' not in t_data:
                return None
            t_data = dict(t_data)
            # legacy YAML compat: 'title' → 'name'
            if 'name' not in t_data and 'title' in t_data:
                t_data['name'] = t_data.pop('title')
            # legacy YAML compat: British 'cancelled' → American 'canceled'
            if t_data.get('status') == 'cancelled':
                t_data['status'] = 'canceled'
            # Early queue writers used ``completed`` for both the ticket and
            # execution terminal.  Project that historical alias as the
            # canonical ``done`` state without rewriting the authoritative
            # YAML or its audit history merely because it was read.
            if t_data.get('status') == 'completed':
                t_data['status'] = 'done'
            execution = t_data.get('execution')
            if isinstance(execution, dict) and execution.get('state') == 'completed':
                t_data['execution'] = {**execution, 'state': 'done'}
            if 'integration' in t_data and isinstance(t_data['integration'], str):
                t_data['labels'] = [t_data.pop('integration')]
            if hasattr(self, '_project_ticket_evidence'):
                t_data = self._project_ticket_evidence(t_data)
            return Ticket(**t_data)
        except Exception as exc:
            # A malformed ticket is skipped so one bad row does not break the
            # whole sprint, but stay loud about it: a silent drop previously
            # masked writers persisting tickets the model could not re-parse.
            logger.warning(
                "skipping unparseable ticket %s: %s",
                t_data.get('id', '<no-id>') if isinstance(t_data, dict) else '<invalid>',
                exc,
            )
            return None

    def _tickets_from_sprint_data(self, sprint_data: dict[str, Any]) -> list[Ticket]:
        tickets_dict = sprint_data.get('tickets') or {}
        tickets: list[Ticket] = []
        for t_data in tickets_dict.values():
            ticket = self._ticket_from_data(t_data)
            if ticket is not None:
                tickets.append(ticket)
        return tickets

    def _tickets_from_sprint_file(self, sprint_file) -> list[Ticket]:
        """Return validated ticket models, reusing an unchanged YAML snapshot.

        ``_read_yaml_cached`` already tracks the file mtime and returns the same
        parsed snapshot while it is current. Model validation used to be
        repeated for every list request, which made the API CPU-bound when a
        dashboard and autonomous controllers inspected a large queue together.
        Cache entries retain the snapshot object as an identity guard, so an
        id reused by Python cannot return models belonging to old data.
        """
        data = self._read_yaml_cached(sprint_file)
        if not data:
            return []
        sprint_data = data.get('sprint') or data
        cache = getattr(self, '_ticket_model_cache', None)
        if cache is None:
            cache = {}
            self._ticket_model_cache = cache
        key = str(sprint_file)
        if not self._yaml_file_cacheable(sprint_file):
            cache.pop(key, None)
            return self._tickets_from_sprint_data(sprint_data)
        ticket_ids = (sprint_data.get('tickets') or {}).keys()
        evidence_revision = (
            self._ticket_evidence_revision(ticket_ids)
            if hasattr(self, '_ticket_evidence_revision')
            else ()
        )
        entry = cache.get(key)
        if entry is not None and entry[0] is sprint_data and entry[2] == evidence_revision:
            return list(entry[1])

        tickets = self._tickets_from_sprint_data(sprint_data)
        cache[key] = (sprint_data, tuple(tickets), evidence_revision)
        return tickets

    def _filter_by_files(self, tickets: list[Ticket], value: Any) -> list[Ticket]:
        patterns = value if isinstance(value, list) else [value]
        return [t for t in tickets if self._matches_files(t, patterns)]

    def _filter_by_labels(self, tickets: list[Ticket], value: Any) -> list[Ticket]:
        labels = value if isinstance(value, list) else [value]
        return [t for t in tickets if any(label in (t.labels or []) for label in labels)]

    def _filter_by_attribute(self, tickets: list[Ticket], key: str, value: Any) -> list[Ticket]:
        def _normalize(v: Any) -> str:
            return v.value if hasattr(v, 'value') else str(v)
        value_str = _normalize(value)
        return [t for t in tickets if _normalize(getattr(t, key, None)) == value_str]

    def _apply_filters(self, tickets: list[Ticket], **filters) -> list[Ticket]:
        result = tickets
        for key, value in filters.items():
            if value is None:
                continue
            if key == 'files':
                result = self._filter_by_files(result, value)
            elif key == 'labels':
                result = self._filter_by_labels(result, value)
            else:
                result = self._filter_by_attribute(result, key, value)
        return result

    def _matches_files(self, ticket: Ticket, patterns: list[str]) -> bool:
        """Check if ticket matches any of the file patterns."""
        # Check files list
        if ticket.files:
            for f in ticket.files:
                for pattern in patterns:
                    if fnmatch.fnmatch(f, pattern):
                        return True
        # Check single file field (backward compatibility)
        if ticket.file:
            for pattern in patterns:
                if fnmatch.fnmatch(ticket.file, pattern):
                    return True
        return False

    def list_tickets(self, sprint: str = 'current', **filters) -> list[Ticket]:
        """List tickets with filters."""
        tickets: list[Ticket] = []
        if sprint == 'all':
            for sprint_file in self._all_sprint_files():
                tickets.extend(self._tickets_from_sprint_file(sprint_file))
        else:
            sprint_file = self._sprint_file(sprint)
            tickets = self._tickets_from_sprint_file(sprint_file)
        return self._apply_filters(tickets, **filters)
