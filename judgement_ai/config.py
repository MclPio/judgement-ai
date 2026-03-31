"""Configuration loading helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file into a dictionary."""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        msg = f"Failed to parse config file {config_path}: {exc}"
        raise ValueError(msg) from exc
    if not isinstance(data, dict):
        msg = f"Configuration root in {config_path} must be a mapping."
        raise ValueError(msg)
    return _expand_env_values(data)


def _expand_env_values(value: Any) -> Any:
    """Recursively expand environment variable references in config values."""
    if isinstance(value, dict):
        return {key: _expand_env_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_values(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value
