from __future__ import annotations

import pytest

from judgement_ai.config import load_config


def test_load_config_rejects_invalid_yaml(tmp_path) -> None:
    config_path = tmp_path / "broken.yaml"
    config_path.write_text("llm: [broken", encoding="utf-8")

    with pytest.raises(ValueError, match=str(config_path)):
        load_config(config_path)


def test_load_config_requires_mapping_root(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("- item\n- item2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a mapping"):
        load_config(config_path)
