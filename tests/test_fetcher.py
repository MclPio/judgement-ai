from __future__ import annotations

import json

import pytest

from judgement_ai.fetcher import (
    FileResultsFetcher,
    InMemoryResultsFetcher,
    SearchResult,
    normalize_result,
    normalize_results_mapping,
)


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


def test_normalize_results_mapping_assigns_default_rank() -> None:
    payload = normalize_results_mapping(
        {
            "vitamin b6": [
                {"doc_id": "123", "fields": {"title": "Vitamin B6 100mg"}},
                {"doc_id": "456", "rank": 7, "fields": {"title": "B Complex"}},
            ]
        },
        source_name="Test payload",
    )

    assert [item.rank for item in payload["vitamin b6"]] == [1, 7]


def test_in_memory_results_fetcher_loads_query_results() -> None:
    fetcher = InMemoryResultsFetcher(
        {
            "vitamin b6": [
                {"doc_id": "123", "fields": {"title": "Vitamin B6 100mg"}},
                {"doc_id": "456", "rank": 7, "fields": {"title": "B Complex"}},
            ]
        }
    )

    results = fetcher.fetch("vitamin b6")

    assert [item.doc_id for item in results] == ["123", "456"]
    assert [item.rank for item in results] == [1, 7]
    assert results[0].fields["title"] == "Vitamin B6 100mg"


def test_in_memory_results_fetcher_accepts_search_result_objects() -> None:
    fetcher = InMemoryResultsFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="123", rank=1, fields={"title": "Vitamin B6 100mg"}),
            ]
        }
    )

    results = fetcher.fetch("vitamin b6")

    assert results == [
        SearchResult(doc_id="123", rank=1, fields={"title": "Vitamin B6 100mg"})
    ]


def test_in_memory_results_fetcher_returns_copy_for_query_results() -> None:
    fetcher = InMemoryResultsFetcher(
        {
            "vitamin b6": [
                {"doc_id": "123", "fields": {"title": "Vitamin B6 100mg"}},
            ]
        }
    )

    results = fetcher.fetch("vitamin b6")
    results.append(SearchResult(doc_id="456", rank=2, fields={}))

    assert [item.doc_id for item in fetcher.fetch("vitamin b6")] == ["123"]


def test_in_memory_results_fetcher_rejects_invalid_top_level_payload() -> None:
    with pytest.raises(ValueError, match="maps each query to a list"):
        InMemoryResultsFetcher([{"query": "vitamin b6"}])


def test_in_memory_results_fetcher_rejects_non_list_query_payload() -> None:
    with pytest.raises(ValueError, match="must be a list of results"):
        InMemoryResultsFetcher({"vitamin b6": {"doc_id": "123"}})


def test_in_memory_results_fetcher_rejects_invalid_result_item() -> None:
    with pytest.raises(ValueError, match="must be an object"):
        InMemoryResultsFetcher({"vitamin b6": ["not a result object"]})
