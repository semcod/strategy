"""Load an untyped strategy mapping without hiding input failures."""
from pathlib import Path
from typing import Any

import yaml


def load_strategy_mapping(path: Path) -> dict[str, Any]:
    """Raise a stable ValueError without embedding private YAML contents."""
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeError:
        raise ValueError('strategy_input_invalid_encoding') from None
    except OSError:
        raise ValueError('strategy_input_unreadable') from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        raise ValueError('strategy_input_invalid_yaml') from None
    if not isinstance(data, dict):
        raise ValueError('strategy_input_not_mapping')
    return data
