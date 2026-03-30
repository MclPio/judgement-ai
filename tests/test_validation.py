from __future__ import annotations

import json
from pathlib import Path

import pytest

from judgement_ai.grader import Grader
from judgement_ai.validation import (
    ValidationFetcher,
    compute_exact_agreement,
    compute_metrics,
    compute_spearman,
    load_validation_rows,
    run_validation_benchmark,
)


class DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def make_grader() -> Grader:
    return Grader(
        fetcher=ValidationFetcher([]),
        llm_base_url="https://api.example.com/v1",
        llm_api_key="test-key",
        llm_model="gpt-test",
        max_workers=2,
        passes=1,
    )


def test_load_validation_rows_reads_dataset() -> None:
    rows = load_validation_rows(Path("validate/datasets/smoke.json"))

    assert rows
    assert rows[0].benchmark == "smoke"


def test_compute_spearman_handles_identical_rankings() -> None:
    assert round(compute_spearman([0, 1, 2, 3], [0, 1, 2, 3]), 6) == 1.0


def test_compute_exact_agreement_returns_fraction() -> None:
    assert compute_exact_agreement([0, 1, 2, 3], [0, 1, 0, 3]) == 0.75


def test_compute_metrics_counts_failures() -> None:
    metrics = compute_metrics(
        [
            {"human_score": 3, "ai_score": 3},
            {"human_score": 1, "failure": {"error": "bad"}},
        ]
    )

    assert metrics["num_rows"] == 2
    assert metrics["num_failed_rows"] == 1


def test_run_validation_benchmark_writes_completed_summary(monkeypatch, tmp_path) -> None:
    responses = iter(
        [
            DummyResponse("Direct match.\nSCORE: 3"),
            DummyResponse("Irrelevant.\nSCORE: 0"),
            DummyResponse("Relevant.\nSCORE: 2"),
        ]
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    result = run_validation_benchmark(
        benchmark="smoke",
        dataset_path=Path("validate/datasets/smoke.json"),
        output_dir=tmp_path,
        grader=make_grader(),
    )

    assert result["summary"]["status"] == "completed"
    assert result["summary"]["metrics"]["num_rows"] == 3
    assert (tmp_path / "smoke-raw-judgments.json").exists()
    assert result["summary"]["max_retries"] == 3
    assert result["summary"]["request_timeout"] == 60.0


def test_run_validation_benchmark_passes_progress_callback(monkeypatch, tmp_path) -> None:
    responses = iter(
        [
            DummyResponse("Direct match.\nSCORE: 3"),
            DummyResponse("Irrelevant.\nSCORE: 0"),
            DummyResponse("Relevant.\nSCORE: 2"),
        ]
    )
    events = []

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return next(responses)

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    run_validation_benchmark(
        benchmark="smoke",
        dataset_path=Path("validate/datasets/smoke.json"),
        output_dir=tmp_path,
        grader=make_grader(),
        progress_callback=events.append,
    )

    assert events[0].event == "start"
    assert events[-1].event == "finished"


def test_run_validation_benchmark_fails_canonical_partial_run(monkeypatch, tmp_path) -> None:
    dataset_path = tmp_path / "amazon_product_search.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "benchmark": "amazon_product_search",
                    "query_id": "q1",
                    "query": "wireless headphones",
                    "doc_id": "p1",
                    "rank": 1,
                    "human_score": 3,
                    "fields": {"title": "Wireless Noise Cancelling Headphones"},
                }
            ]
        ),
        encoding="utf-8",
    )

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        return DummyResponse("Missing strict output")

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    result = run_validation_benchmark(
        benchmark="amazon_product_search",
        dataset_path=dataset_path,
        output_dir=tmp_path,
        grader=make_grader(),
    )

    assert result["summary"]["status"] == "failed"
    assert result["summary"]["metrics"]["num_failed_rows"] > 0


def test_run_validation_benchmark_resume_skips_completed_rows(monkeypatch, tmp_path) -> None:
    dataset_path = Path("validate/datasets/smoke.json")
    raw_path = tmp_path / "smoke-raw-judgments.json"
    raw_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "smoke-doc-1",
                    "score": 3,
                    "reasoning": "Already scored",
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
        return DummyResponse("Relevant.\nSCORE: 2")

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    result = run_validation_benchmark(
        benchmark="smoke",
        dataset_path=dataset_path,
        output_dir=tmp_path,
        grader=make_grader(),
        resume=True,
    )

    assert calls["count"] == 2
    assert result["summary"]["metrics"]["num_scored_rows"] == 3
    assert result["summary"]["resume"] is True


def test_run_validation_benchmark_retry_failures_only_reruns_failed_rows(
    monkeypatch, tmp_path
) -> None:
    dataset_path = Path("validate/datasets/smoke.json")
    raw_path = tmp_path / "smoke-raw-judgments.json"
    raw_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "smoke-doc-1",
                    "score": 3,
                    "reasoning": "Already scored",
                    "rank": 1,
                },
                {
                    "query": "vitamin b6",
                    "doc_id": "smoke-doc-2",
                    "score": 0,
                    "reasoning": "Already scored",
                    "rank": 2,
                },
            ]
        ),
        encoding="utf-8",
    )
    failures_path = tmp_path / "previous-failures.json"
    failures_path.write_text(
        json.dumps(
            [
                {
                    "query": "magnesium for sleep",
                    "doc_id": "smoke-doc-3",
                    "rank": 1,
                    "failure_type": "parse_error",
                    "error": "bad format",
                    "attempts": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    calls = {"count": 0}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        calls["count"] += 1
        return DummyResponse("Relevant.\nSCORE: 2")

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    result = run_validation_benchmark(
        benchmark="smoke",
        dataset_path=dataset_path,
        output_dir=tmp_path,
        grader=make_grader(),
        retry_failures_from=failures_path,
    )

    assert calls["count"] == 1
    assert result["summary"]["retry_failures_from"] == str(failures_path)
    assert result["summary"]["metrics"]["num_failed_rows"] == 0
    assert not (tmp_path / "smoke-failures.json").exists()


def test_run_validation_benchmark_retry_sweep_requires_existing_raw_judgments(
    tmp_path,
) -> None:
    failures_path = tmp_path / "previous-failures.json"
    failures_path.write_text(
        json.dumps(
            [
                {
                    "query": "magnesium for sleep",
                    "doc_id": "smoke-doc-3",
                    "rank": 1,
                    "failure_type": "parse_error",
                    "error": "bad format",
                    "attempts": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="existing raw judgments file"):
        run_validation_benchmark(
            benchmark="smoke",
            dataset_path=Path("validate/datasets/smoke.json"),
            output_dir=tmp_path,
            grader=make_grader(),
            retry_failures_from=failures_path,
        )


def test_results_index_mentions_both_benchmarks() -> None:
    payload = json.loads(Path("validate/results.json").read_text(encoding="utf-8"))

    assert "smoke" in payload["benchmarks"]
    assert "amazon_product_search" in payload["benchmarks"]
