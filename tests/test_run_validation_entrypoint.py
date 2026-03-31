from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path("validate/run_validation.py")


def load_module():
    spec = importlib.util.spec_from_file_location("validate_run_validation", MODULE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_gate_failure_message_is_explicit(tmp_path) -> None:
    module = load_module()
    gate_path = tmp_path / "amazon_product_search_calibration-reference-gate.json"
    gate_path.write_text(
        json.dumps(
            {
                "passed": False,
                "failed_reasons": ["spearman_at_least_0_40", "no_score_collapse"],
                "metrics": {"spearman": 0.304068},
                "analysis": {"failure_counts_by_type": {}, "warnings": []},
            }
        ),
        encoding="utf-8",
    )

    assert (
        module._gate_failure_message(gate_path)
        == "spearman 0.304068 < 0.40, score collapse warning"
    )


def test_full_benchmark_requires_only_reference_gate(tmp_path) -> None:
    module = load_module()
    local_gate = tmp_path / "amazon_product_search_calibration-local-gate.json"
    reference_gate = tmp_path / "amazon_product_search_calibration-reference-gate.json"
    local_gate.write_text(
        json.dumps({"passed": False, "failed_reasons": ["failure_rate_at_most_5_percent"]}),
        encoding="utf-8",
    )
    reference_gate.write_text(
        json.dumps(
            {
                "passed": True,
                "failed_reasons": [],
                "metrics": {"spearman": 0.61},
                "analysis": {"failure_counts_by_type": {}, "warnings": []},
            }
        ),
        encoding="utf-8",
    )

    module._require_calibration_gates(tmp_path)


def test_full_benchmark_blocks_when_reference_gate_fails(tmp_path) -> None:
    module = load_module()
    reference_gate = tmp_path / "amazon_product_search_calibration-reference-gate.json"
    reference_gate.write_text(
        json.dumps(
            {
                "passed": False,
                "failed_reasons": ["no_parse_failures"],
                "metrics": {"spearman": 0.52},
                "analysis": {"failure_counts_by_type": {"parse_error": 3}, "warnings": []},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Reference calibration failed: 3 parse failures"):
        module._require_calibration_gates(tmp_path)
