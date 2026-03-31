from pathlib import Path

import pytest

from judgement_ai.validation_prep import (
    build_benchmark_report,
    filter_esci_rows,
    label_counts,
    load_esci_rows,
    stratified_sample_rows,
)


def test_stratified_sample_rows_is_query_balanced_and_deterministic() -> None:
    rows = [
        {"query": "q1", "query_id": "q1", "doc_id": "a1", "rank": 1, "human_score": 1},
        {"query": "q1", "query_id": "q1", "doc_id": "a2", "rank": 2, "human_score": 1},
        {"query": "q2", "query_id": "q2", "doc_id": "b1", "rank": 1, "human_score": 1},
        {"query": "q3", "query_id": "q3", "doc_id": "c1", "rank": 1, "human_score": 1},
        {"query": "q4", "query_id": "q4", "doc_id": "d1", "rank": 1, "human_score": 3},
        {"query": "q5", "query_id": "q5", "doc_id": "e1", "rank": 1, "human_score": 3},
    ]

    sampled = stratified_sample_rows(rows, per_label=3)

    assert sampled == [
        {"query": "q1", "query_id": "q1", "doc_id": "a1", "rank": 1, "human_score": 1},
        {"query": "q2", "query_id": "q2", "doc_id": "b1", "rank": 1, "human_score": 1},
        {"query": "q3", "query_id": "q3", "doc_id": "c1", "rank": 1, "human_score": 1},
        {"query": "q4", "query_id": "q4", "doc_id": "d1", "rank": 1, "human_score": 3},
        {"query": "q5", "query_id": "q5", "doc_id": "e1", "rank": 1, "human_score": 3},
    ]


def test_label_counts_returns_sorted_mapping() -> None:
    counts = label_counts(
        [
            {"human_score": 3},
            {"human_score": 0},
            {"human_score": 3},
        ]
    )

    assert counts == {0: 1, 3: 2}


def test_load_esci_rows_supports_csv(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,product_title\n"
        "water bottle,p1,E,Insulated Bottle\n",
        encoding="utf-8",
    )

    rows = load_esci_rows(path)

    assert rows[0]["query"] == "water bottle"
    assert rows[0]["product_id"] == "p1"


def test_load_esci_rows_merges_examples_and_products_from_directory(monkeypatch, tmp_path) -> None:
    directory = tmp_path / "esci"
    directory.mkdir()
    examples = directory / "shopping_queries_dataset_examples.parquet"
    products = directory / "shopping_queries_dataset_products.parquet"
    examples.write_text("", encoding="utf-8")
    products.write_text("", encoding="utf-8")

    def fake_read(path: Path):
        if path == examples:
            return [
                {
                    "query": "water bottle",
                    "product_id": "p1",
                    "product_locale": "us",
                    "esci_label": "E",
                }
            ]
        if path == products:
            return [
                {
                    "product_id": "p1",
                    "product_locale": "us",
                    "product_title": "Insulated Bottle",
                    "product_brand": "Hydra",
                }
            ]
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr("judgement_ai.validation_prep._read_tabular_rows", fake_read)

    rows = load_esci_rows(directory)

    assert rows == [
        {
            "query": "water bottle",
            "product_id": "p1",
            "product_locale": "us",
            "esci_label": "E",
            "product_title": "Insulated Bottle",
            "product_brand": "Hydra",
        }
    ]


def test_load_esci_rows_fails_if_product_metadata_is_missing(tmp_path) -> None:
    directory = tmp_path / "esci"
    directory.mkdir()
    (directory / "shopping_queries_dataset_examples.parquet").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain shopping_queries_dataset_examples"):
        load_esci_rows(directory)


def test_filter_esci_rows_applies_locale_and_small_version() -> None:
    rows = [
        {"product_locale": "us", "small_version": "1"},
        {"product_locale": "us", "small_version": "0"},
        {"product_locale": "es", "small_version": "1"},
    ]

    filtered = filter_esci_rows(rows, locale="us", reduced_task_only=True)

    assert filtered == [{"product_locale": "us", "small_version": "1"}]


def test_build_benchmark_report_counts_queries_and_blankish_fields() -> None:
    candidate_rows = [
        {
            "query": "water bottle",
            "human_score": 3,
            "fields": {"title": "Bottle", "brand": "Hydra", "description": "nan"},
        },
        {
            "query": "water bottle",
            "human_score": 2,
            "fields": {"title": "Alt Bottle", "brand": "", "description": "Steel"},
        },
    ]
    benchmark_rows = [candidate_rows[0]]

    report = build_benchmark_report(candidate_rows, benchmark_rows)

    assert report["candidate_total_rows"] == 2
    assert report["benchmark_total_rows"] == 1
    assert report["candidate_unique_queries"] == 1
    assert report["top_query_frequencies"] == [{"query": "water bottle", "count": 1}]
    assert report["candidate_blankish_counts"]["brand"] == 1
    assert report["candidate_blankish_counts"]["description"] == 1


def test_provenance_files_exist() -> None:
    assert Path("validate/provenance/amazon_product_search.md").exists()
