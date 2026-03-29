from __future__ import annotations

import json

import pytest

from judgement_ai.fetcher import ElasticsearchFetcher, FileResultsFetcher, normalize_result


class DummyResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._payload


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


def test_elasticsearch_fetcher_normalizes_hits(monkeypatch) -> None:
    calls = {}

    def fake_get(url: str, *, params, timeout):
        calls["url"] = url
        calls["params"] = params
        calls["timeout"] = timeout
        return DummyResponse(
            {
                "hits": {
                    "hits": [
                        {"_id": "123", "_source": {"title": "Vitamin B6 100mg"}},
                        {"_id": "456", "_source": {"title": "Energy Support"}},
                    ]
                }
            }
        )

    monkeypatch.setattr("judgement_ai.fetcher.requests.get", fake_get)

    fetcher = ElasticsearchFetcher(url="https://search.example.com/catalog", top_n=24)
    results = fetcher.fetch("vitamin b6")

    assert calls["url"] == "https://search.example.com/catalog/_search"
    assert calls["params"] == {"size": 24, "q": "vitamin b6"}
    assert len(results) == 2
    assert results[0].doc_id == "123"
    assert results[0].rank == 1
    assert results[1].rank == 2


def test_elasticsearch_fetcher_wraps_request_errors(monkeypatch) -> None:
    def fake_get(url: str, *, params, timeout):
        del url, params, timeout
        raise OSError("network down")

    monkeypatch.setattr("judgement_ai.fetcher.requests.get", fake_get)

    fetcher = ElasticsearchFetcher(url="https://search.example.com/catalog")

    with pytest.raises(RuntimeError, match="Failed to fetch results"):
        fetcher.fetch("vitamin b6")

