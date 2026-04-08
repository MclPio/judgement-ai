from __future__ import annotations

import json

import pytest
import requests

from judgement_ai.fetcher import SearchResult
from judgement_ai.grading import GradeProgress, Grader, ParseError, ProviderError


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


class ErrorResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


def make_grader(
    *,
    fetcher: StaticFetcher | None = None,
    passes: int = 1,
    provider: str = "openai_compatible",
    response_mode: str = "text",
    think: bool | None = None,
    max_retries: int = 3,
    request_timeout: float = 60.0,
    temperature: float = 0.0,
) -> Grader:
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
        max_retries=max_retries,
        request_timeout=request_timeout,
        temperature=temperature,
        provider=provider,
        response_mode=response_mode,
        think=think,
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


def test_parse_response_accepts_score_variants_in_fallback_mode() -> None:
    grader = make_grader()

    score, reasoning = grader.parse_response(
        "**Relevance Score:** 1\nBrand mismatch.",
        allow_variants=True,
    )

    assert score == 1
    assert reasoning == ""


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

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader()
    response = grader._call_llm(prompt="Prompt text")

    assert response == "Reasoning.\nSCORE: 2"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["temperature"] == 0
    assert captured["json"]["messages"][0]["content"] == "Prompt text"
    assert captured["timeout"] == 60.0


def test_call_llm_uses_configured_temperature(monkeypatch) -> None:
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        captured["json"] = json
        return DummyResponse(
            {"choices": [{"message": {"content": "Reasoning.\nSCORE: 2"}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(temperature=0.35)
    grader._call_llm(prompt="Prompt text")

    assert captured["json"]["temperature"] == 0.35


def test_grader_rejects_negative_temperature() -> None:
    with pytest.raises(ValueError, match="temperature must be greater than or equal to 0"):
        make_grader(temperature=-0.1)


def test_call_llm_uses_openai_json_schema_payload(monkeypatch) -> None:
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {"choices": [{"message": {"content": '{"score": 2, "reasoning": "Clear fit."}'}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(response_mode="json_schema")
    response = grader._call_llm(prompt="Prompt text")

    assert response == {"score": 2, "reasoning": "Clear fit."}
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["json"]["response_format"]["type"] == "json_schema"
    assert captured["json"]["response_format"]["json_schema"]["schema"]["required"] == [
        "score",
        "reasoning",
    ]
    assert "notes" not in captured["json"]["response_format"]["json_schema"]["schema"]["properties"]
    assert (
        "refusal" not in captured["json"]["response_format"]["json_schema"]["schema"]["properties"]
    )


def test_call_llm_uses_ollama_native_api_for_structured_output(monkeypatch) -> None:
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {"message": {"content": '{"score": 3, "reasoning": "Exact match."}'}}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = Grader(
        fetcher=StaticFetcher({}),
        llm_base_url="http://localhost:11434/v1",
        llm_api_key=None,
        llm_model="qwen3.5:9b",
        provider="ollama",
        response_mode="json_schema",
        think=False,
        temperature=0.2,
    )
    response = grader._call_llm(prompt="Prompt text")

    assert response == {"score": 3, "reasoning": "Exact match."}
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["think"] is False
    assert captured["json"]["options"]["temperature"] == 0.2
    assert captured["json"]["format"]["required"] == ["score", "reasoning"]


def test_call_llm_includes_response_body_in_provider_errors(monkeypatch) -> None:
    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        response = ErrorResponse(400, '{"error":"unsupported parameter: response_format"}')
        raise requests.HTTPError("400 Client Error", response=response)

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(response_mode="json_schema")

    with pytest.raises(ProviderError, match="unsupported parameter"):
        grader._call_llm(prompt="Prompt text")


def test_call_llm_suggests_text_mode_for_json_schema_400s(monkeypatch) -> None:
    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        response = ErrorResponse(400, "bad request")
        raise requests.HTTPError("400 Client Error", response=response)

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(response_mode="json_schema")

    with pytest.raises(ProviderError, match="retry with text mode"):
        grader._call_llm(prompt="Prompt text")


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

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

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
    assert grader.last_summary == {"successes": 2, "failures": 0, "skipped": 0}


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

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

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
    assert grader.last_summary == {"successes": 1, "failures": 1, "skipped": 0}

    payload = json.loads(failed_log_path.read_text(encoding="utf-8"))
    assert payload[0]["doc_id"] == "bad"
    assert payload[0]["attempts"] == 3
    assert payload[0]["failure_type"] == "parse_error"
    assert "raw_response" in payload[0]


def test_grade_writes_failures_incrementally(monkeypatch, tmp_path) -> None:
    failed_log_path = tmp_path / "failed.json"
    seen = {}
    responses = iter(
        [
            DummyResponse({"choices": [{"message": {"content": "Missing strict output"}}]}),
            DummyResponse({"choices": [{"message": {"content": "Useful result.\nSCORE: 2"}}]}),
        ]
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    def item_callback(item):
        if item.__class__.__name__ == "GradeFailure":
            seen["payload"] = json.loads(failed_log_path.read_text(encoding="utf-8"))

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)
    fetcher = StaticFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="bad", rank=1, fields={"title": "Unknown"}),
                SearchResult(doc_id="good", rank=2, fields={"title": "Vitamin B6 100mg"}),
            ]
        }
    )
    grader = make_grader(fetcher=fetcher, max_retries=1)
    grader.grade(
        queries=["vitamin b6"],
        failed_log_path=failed_log_path,
        item_callback=item_callback,
    )

    assert seen["payload"][0]["doc_id"] == "bad"


def test_grade_respects_configured_timeout_and_retry_count(monkeypatch, tmp_path) -> None:
    calls = {"count": 0, "timeout": None}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json
        calls["count"] += 1
        calls["timeout"] = timeout
        raise RuntimeError("provider down")

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = Grader(
        fetcher=StaticFetcher(
            {
                "vitamin b6": [
                    SearchResult(doc_id="123", rank=1, fields={"title": "Vitamin B6 100mg"})
                ]
            }
        ),
        llm_base_url="https://api.example.com/v1",
        llm_api_key="test-key",
        llm_model="gpt-test",
        max_workers=1,
        max_retries=1,
        request_timeout=120.0,
        provider="openai_compatible",
    )

    failed_log_path = tmp_path / "failed.json"
    grader.grade(queries=["vitamin b6"], failed_log_path=failed_log_path)

    payload = json.loads(failed_log_path.read_text(encoding="utf-8"))
    assert calls["count"] == 1
    assert calls["timeout"] == 120.0
    assert payload[0]["attempts"] == 1
    assert payload[0]["failure_type"] == "unknown_error"


def test_grade_classifies_timeout_failures(monkeypatch, tmp_path) -> None:
    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        raise requests.Timeout("slow")

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader()
    failed_log_path = tmp_path / "failed.json"
    grader.grade(queries=["vitamin b6"], failed_log_path=failed_log_path)

    payload = json.loads(failed_log_path.read_text(encoding="utf-8"))
    assert payload[0]["failure_type"] == "timeout"


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

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(passes=3)
    results = grader.grade(queries=["vitamin b6"], failed_log_path=None)

    assert results[0].score == 3
    assert results[0].pass_scores == [3, 2, 3]


def test_grade_skips_completed_pairs_when_resuming(monkeypatch, tmp_path) -> None:
    resume_path = tmp_path / "judgments.json"
    resume_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "123",
                    "score": 3,
                    "reasoning": "Already done.",
                    "rank": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    calls = {"count": 0}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        calls["count"] += 1
        return DummyResponse(
            {"choices": [{"message": {"content": "Needs grading.\nSCORE: 2"}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    fetcher = StaticFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="123", rank=1, fields={"title": "Done already"}),
                SearchResult(doc_id="456", rank=2, fields={"title": "New item"}),
            ]
        }
    )
    grader = make_grader(fetcher=fetcher)

    results = grader.grade(
        queries=["vitamin b6"],
        resume_from=resume_path,
        failed_log_path=None,
    )

    assert calls["count"] == 1
    assert [item.doc_id for item in results] == ["456"]
    assert grader.last_summary == {"successes": 1, "failures": 0, "skipped": 1}


def test_grade_writes_incremental_json_output(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "judgments.json"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader()
    grader.grade(
        queries=["vitamin b6"],
        output_path=output_path,
        output_format="json",
        failed_log_path=None,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload[0]["doc_id"] == "123"


def test_grade_rejects_non_json_runtime_output_format(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "judgments.json"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader()
    with pytest.raises(ValueError, match="output_format must be 'json' or None"):
        grader.grade(
            queries=["vitamin b6"],
            output_path=output_path,
            output_format="csv",
            failed_log_path=None,
        )


def test_grade_emits_progress_events_for_start_skip_and_finish(monkeypatch, tmp_path) -> None:
    resume_path = tmp_path / "judgments.json"
    resume_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "123",
                    "score": 3,
                    "reasoning": "Already done.",
                    "rank": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    events: list[GradeProgress] = []

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse(
            {"choices": [{"message": {"content": "Needs grading.\nSCORE: 2"}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    fetcher = StaticFetcher(
        {
            "vitamin b6": [
                SearchResult(doc_id="123", rank=1, fields={"title": "Done already"}),
                SearchResult(doc_id="456", rank=2, fields={"title": "New item"}),
            ]
        }
    )
    grader = make_grader(fetcher=fetcher)

    grader.grade(
        queries=["vitamin b6"],
        resume_from=resume_path,
        failed_log_path=None,
        progress_callback=events.append,
    )

    assert [event.event for event in events] == ["start", "item_completed", "finished"]
    assert events[0].skipped == 1
    assert events[0].total == 1
    assert events[-1].successes == 1
    assert events[-1].skipped == 1


def test_grade_emits_failure_progress_event(monkeypatch) -> None:
    events: list[GradeProgress] = []

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse({"choices": [{"message": {"content": "Missing score"}}]})

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader()
    grader.grade(
        queries=["vitamin b6"],
        failed_log_path=None,
        progress_callback=events.append,
    )

    assert "item_failed" in [event.event for event in events]


def test_grade_parses_structured_response_end_to_end(monkeypatch) -> None:
    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse(
            {"choices": [{"message": {"content": '{"score": 3, "reasoning": "Exact fit."}'}}]}
        )

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    grader = make_grader(response_mode="json_schema")
    results = grader.grade(queries=["vitamin b6"], failed_log_path=None)

    assert results[0].score == 3
    assert results[0].reasoning == "Exact fit."
