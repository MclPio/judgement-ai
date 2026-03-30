from __future__ import annotations

import json
from pathlib import Path

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


def test_results_index_mentions_both_benchmarks() -> None:
    payload = json.loads(Path("validate/results.json").read_text(encoding="utf-8"))

    assert "smoke" in payload["benchmarks"]
    assert "amazon_product_search" in payload["benchmarks"]
