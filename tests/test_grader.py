from __future__ import annotations

import json

import pytest

from judgement_ai.fetcher import SearchResult
from judgement_ai.grader import Grader, ParseError


class StaticFetcher:
    def __init__(self, mapping: dict[str, list[SearchResult]]) -> None:
        self.mapping = mapping

    def fetch(self, query: str) -> list[SearchResult]:
        return list(self.mapping.get(query, []))


class DummyResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self.payload


def make_grader(*, fetcher: StaticFetcher | None = None, passes: int = 1) -> Grader:
    return Grader(
        fetcher=fetcher
        or StaticFetcher(
            {
                "vitamin b6": [
                    SearchResult(
                        doc_id="123",
                        rank=1,
                        fields={"title": "Vitamin B6 100mg"},
                    )
                ]
            }
        ),
        llm_base_url="https://api.example.com/v1",
        llm_api_key="test-key",
        llm_model="gpt-test",
        passes=passes,
        max_workers=4,
    )


def test_parse_response_extracts_reasoning_and_score() -> None:
    grader = make_grader()

    score, reasoning = grader.parse_response(
        "This result directly answers the query.\nIt is an exact product match.\nSCORE: 3"
    )

    assert score == 3
    assert "exact product match" in reasoning


def test_parse_response_rejects_missing_score() -> None:
    grader = make_grader()

    with pytest.raises(ParseError, match="SCORE"):
        grader.parse_response("This looks relevant.")


def test_parse_response_rejects_out_of_range_score() -> None:
    grader = make_grader()

    with pytest.raises(ParseError, match="outside the allowed range"):
        grader.parse_response("Reasoning first.\nSCORE: 10")


def test_select_final_score_prefers_majority() -> None:
    grader = make_grader()

    assert grader._select_final_score([3, 3, 2]) == 3


def test_select_final_score_uses_middle_value_when_all_different() -> None:
    grader = make_grader()

    assert grader._select_final_score([0, 3, 2]) == 2


def test_call_llm_uses_openai_compatible_payload(monkeypatch) -> None:
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Reasoning.\nSCORE: 2"}}]}
        )

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    grader = make_grader()
    response = grader._call_llm(prompt="Prompt text")

    assert response == "Reasoning.\nSCORE: 2"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["temperature"] == 0
    assert captured["json"]["messages"][0]["content"] == "Prompt text"


def test_grade_returns_scored_results(monkeypatch) -> None:
    responses = iter(
        [
            DummyResponse({"choices": [{"message": {"content": "Strong match.\nSCORE: 3"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Somewhat relevant.\nSCORE: 2"}}]}),
        ]
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    fetcher = StaticFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="123", rank=2, fields={"title": "B Complex"}),
                SearchResult(doc_id="456", rank=1, fields={"title": "Vitamin B6 100mg"}),
            ]
        }
    )
    grader = make_grader(fetcher=fetcher)
    results = grader.grade(queries=["vitamin b6"], failed_log_path=None)

    assert [item.doc_id for item in results] == ["456", "123"]
    assert [item.score for item in results] == [2, 3]
    assert grader.last_summary == {"successes": 2, "failures": 0}


def test_grade_retries_failures_logs_failed_items_and_continues(monkeypatch, tmp_path) -> None:
    responses = iter(
        [
            DummyResponse({"choices": [{"message": {"content": "Missing strict output"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Still wrong"}}]}),
            DummyResponse({"choices": [{"message": {"content": "No score here either"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Useful result.\nSCORE: 2"}}]}),
        ]
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    fetcher = StaticFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="bad", rank=1, fields={"title": "Unknown"}),
                SearchResult(doc_id="good", rank=2, fields={"title": "Vitamin B6 100mg"}),
            ]
        }
    )
    grader = make_grader(fetcher=fetcher)
    failed_log_path = tmp_path / "failed.json"

    results = grader.grade(
        queries=["vitamin b6"],
        failed_log_path=failed_log_path,
    )

    assert [item.doc_id for item in results] == ["good"]
    assert grader.last_summary == {"successes": 1, "failures": 1}

    payload = json.loads(failed_log_path.read_text(encoding="utf-8"))
    assert payload[0]["doc_id"] == "bad"
    assert payload[0]["attempts"] == 3
    assert "raw_response" in payload[0]


def test_grade_collects_pass_scores(monkeypatch) -> None:
    responses = iter(
        [
            DummyResponse({"choices": [{"message": {"content": "Good.\nSCORE: 3"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Still good.\nSCORE: 2"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Definitely good.\nSCORE: 3"}}]}),
        ]
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    grader = make_grader(passes=3)
    results = grader.grade(queries=["vitamin b6"], failed_log_path=None)

    assert results[0].score == 3
    assert results[0].pass_scores == [3, 2, 3]
