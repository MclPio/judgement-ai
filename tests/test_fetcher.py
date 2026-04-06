from __future__ import annotations

import json

import pytest

from judgement_ai.fetcher import FileResultsFetcher, normalize_result


def test_normalize_result_requires_doc_id() -> None:
    with pytest.raises(ValueError, match="doc_id"):
        normalize_result({"fields": {"title": "Vitamin B6"}}, default_rank=1)


def test_file_results_fetcher_loads_query_results(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {
                        "doc_id": "123",
                        "fields": {"title": "Vitamin B6 100mg"},
                    },
                    {
                        "doc_id": "456",
                        "rank": 7,
                        "fields": {"title": "B Complex"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    fetcher = FileResultsFetcher(path)
    results = fetcher.fetch("vitamin b6")

    assert [item.doc_id for item in results] == ["123", "456"]
    assert [item.rank for item in results] == [1, 7]
    assert results[0].fields["title"] == "Vitamin B6 100mg"


def test_file_results_fetcher_returns_empty_list_for_unknown_query(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"vitamin b6": []}), encoding="utf-8")

    fetcher = FileResultsFetcher(path)

    assert fetcher.fetch("magnesium") == []


def test_file_results_fetcher_rejects_invalid_top_level_payload(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(json.dumps([{"query": "vitamin b6"}]), encoding="utf-8")

    fetcher = FileResultsFetcher(path)

    with pytest.raises(ValueError, match="maps each query to a list"):
        fetcher.fetch("vitamin b6")


def test_file_results_fetcher_rejects_non_list_query_payload(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"vitamin b6": {"doc_id": "123"}}), encoding="utf-8")

    fetcher = FileResultsFetcher(path)

    with pytest.raises(ValueError, match="must be a list"):
        fetcher.fetch("vitamin b6")


def test_file_results_fetcher_reports_invalid_json_path(tmp_path) -> None:
    path = tmp_path / "results.json"
    path.write_text("{not json", encoding="utf-8")

    fetcher = FileResultsFetcher(path)

    with pytest.raises(ValueError, match=str(path)):
        fetcher.fetch("vitamin b6")

