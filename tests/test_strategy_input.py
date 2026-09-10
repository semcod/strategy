"""Invalid strategy input must not produce successful empty work or TODO writes."""
from pathlib import Path

import pytest

from planfile.ticket_validation import validate_planfile_tickets
from planfile.todo_sync import sync_todo_checkboxes_from_planfile


@pytest.mark.parametrize('consumer', ['validate', 'sync'])
@pytest.mark.parametrize('raw,code', [
    (None, 'strategy_input_unreadable'),
    (b'tasks: [PRIVATE_CONTENT', 'strategy_input_invalid_yaml'),
    (b'\xff', 'strategy_input_invalid_encoding'),
    (b'- not-a-mapping\n', 'strategy_input_not_mapping'),
    (b'', 'strategy_input_not_mapping'),
])
def test_invalid_strategy_cannot_look_like_empty_success(tmp_path, consumer, raw, code):
    strategy = tmp_path / 'planfile.yaml'
    if raw is not None:
        strategy.write_bytes(raw)
    todo = tmp_path / 'TODO.md'
    before = '- [ ] TASK-1234\n'
    todo.write_text(before)
    with pytest.raises(ValueError, match=code) as error:
        if consumer == 'validate':
            validate_planfile_tickets(strategy, tmp_path)
        else:
            sync_todo_checkboxes_from_planfile(
                strategy, tmp_path, enabled=True,
                results=[{'id': 'TASK-1234', 'status': 'done'}])
    assert 'PRIVATE_CONTENT' not in str(error.value)
    assert todo.read_text() == before


def test_empty_mapping_is_valid_input(tmp_path):
    strategy = tmp_path / 'planfile.yaml'
    strategy.write_text('{}\n')
    assert validate_planfile_tickets(strategy, tmp_path)['total'] == 0
    assert sync_todo_checkboxes_from_planfile(strategy, tmp_path)['updated'] == 0
