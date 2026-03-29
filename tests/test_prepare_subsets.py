import importlib.util
from pathlib import Path


def load_stratified_sample_rows():
    spec = importlib.util.spec_from_file_location(
        "validate_prepare_subsets",
        Path("validate/prepare_subsets.py"),
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.stratified_sample_rows


def test_stratified_sample_rows_is_deterministic_per_label() -> None:
    stratified_sample_rows = load_stratified_sample_rows()
    rows = [
        {"query_id": "q2", "doc_id": "b", "human_score": 1},
        {"query_id": "q1", "doc_id": "a", "human_score": 1},
        {"query_id": "q3", "doc_id": "c", "human_score": 3},
        {"query_id": "q4", "doc_id": "d", "human_score": 3},
    ]

    sampled = stratified_sample_rows(rows, per_label=1)

    assert sampled == [
        {"query_id": "q1", "doc_id": "a", "human_score": 1},
        {"query_id": "q3", "doc_id": "c", "human_score": 3},
    ]


def test_provenance_files_exist() -> None:
    assert Path("validate/provenance/trec_dl_passage.md").exists()
    assert Path("validate/provenance/trec_product_search.md").exists()
