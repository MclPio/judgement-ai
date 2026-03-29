"""Validation helpers and benchmark orchestration."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from judgement_ai.fetcher import SearchResult
from judgement_ai.grader import GradeFailure, Grader
from judgement_ai.models import GradeResult


@dataclass(slots=True)
class ValidationRow:
    """One human-labeled validation item."""

    benchmark: str
    query_id: str
    query: str
    doc_id: str
    rank: int
    human_score: int
    fields: dict[str, Any]


class ValidationFetcher:
    """Fetcher backed by checked-in validation rows."""

    def __init__(self, rows: list[ValidationRow]) -> None:
        grouped: dict[str, list[SearchResult]] = defaultdict(list)
        for row in rows:
            grouped[row.query].append(
                SearchResult(doc_id=row.doc_id, rank=row.rank, fields=row.fields)
            )
        for query in grouped:
            grouped[query].sort(key=lambda item: (item.rank, item.doc_id))
        self._grouped = dict(grouped)

    def fetch(self, query: str) -> list[SearchResult]:
        """Return validation items for a query."""
        return list(self._grouped.get(query, []))


def load_validation_rows(path: str | Path) -> list[ValidationRow]:
    """Load benchmark rows from a checked-in JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Validation dataset must be a JSON list of rows.")

    rows: list[ValidationRow] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each validation row must be a JSON object.")
        fields = item.get("fields")
        if not isinstance(fields, dict):
            raise ValueError("Each validation row must include an object-valued 'fields'.")
        rows.append(
            ValidationRow(
                benchmark=str(item["benchmark"]),
                query_id=str(item["query_id"]),
                query=str(item["query"]),
                doc_id=str(item["doc_id"]),
                rank=int(item.get("rank", 1)),
                human_score=int(item["human_score"]),
                fields=fields,
            )
        )
    return rows


def average_ranks(values: list[int]) -> list[float]:
    """Return average ranks for tied values."""
    sorted_positions = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)

    position = 0
    while position < len(sorted_positions):
        end = position
        while (
            end + 1 < len(sorted_positions)
            and values[sorted_positions[end + 1]] == values[sorted_positions[position]]
        ):
            end += 1

        average_rank = (position + end + 2) / 2.0
        for offset in range(position, end + 1):
            ranks[sorted_positions[offset]] = average_rank
        position = end + 1

    return ranks


def compute_spearman(human_scores: list[int], ai_scores: list[int]) -> float:
    """Compute Spearman correlation with average ranks for ties."""
    if len(human_scores) != len(ai_scores):
        raise ValueError("human_scores and ai_scores must have the same length.")
    if len(human_scores) < 2:
        return 1.0

    human_ranks = average_ranks(human_scores)
    ai_ranks = average_ranks(ai_scores)
    return pearson_correlation(human_ranks, ai_ranks)


def pearson_correlation(left: list[float], right: list[float]) -> float:
    """Compute Pearson correlation between two numeric lists."""
    if len(left) != len(right):
        raise ValueError("Inputs must have the same length.")

    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    covariance = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)

    if left_variance == 0 or right_variance == 0:
        return 0.0

    return covariance / (left_variance ** 0.5 * right_variance ** 0.5)


def compute_exact_agreement(human_scores: list[int], ai_scores: list[int]) -> float:
    """Compute exact score agreement as a fraction in [0, 1]."""
    if len(human_scores) != len(ai_scores):
        raise ValueError("human_scores and ai_scores must have the same length.")
    if not human_scores:
        return 0.0

    matches = sum(
        1
        for human_score, ai_score in zip(human_scores, ai_scores, strict=True)
        if human_score == ai_score
    )
    return matches / len(human_scores)


def align_judgments(
    rows: list[ValidationRow],
    results: list[GradeResult],
    failures: list[GradeFailure],
) -> list[dict[str, Any]]:
    """Combine benchmark rows with AI outputs and failures."""
    result_lookup = {(result.query, result.doc_id): result for result in results}
    failure_lookup = {(failure.query, failure.doc_id): failure for failure in failures}

    aligned: list[dict[str, Any]] = []
    for row in rows:
        result = result_lookup.get((row.query, row.doc_id))
        failure = failure_lookup.get((row.query, row.doc_id))
        payload = {
            "benchmark": row.benchmark,
            "query_id": row.query_id,
            "query": row.query,
            "doc_id": row.doc_id,
            "rank": row.rank,
            "human_score": row.human_score,
            "fields": row.fields,
        }
        if result is not None:
            payload.update(
                {
                    "ai_score": result.score,
                    "ai_reasoning": result.reasoning,
                    **({"pass_scores": result.pass_scores} if result.pass_scores else {}),
                }
            )
        elif failure is not None:
            payload.update(
                {
                    "failure": {
                        "error": failure.error,
                        "attempts": failure.attempts,
                        **(
                            {"raw_response": failure.raw_response}
                            if failure.raw_response is not None
                            else {}
                        ),
                    }
                }
            )
        aligned.append(payload)
    return aligned


def compute_metrics(aligned_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary metrics from aligned benchmark rows."""
    successful_rows = [row for row in aligned_rows if "ai_score" in row]
    human_scores = [int(row["human_score"]) for row in successful_rows]
    ai_scores = [int(row["ai_score"]) for row in successful_rows]

    return {
        "num_rows": len(aligned_rows),
        "num_scored_rows": len(successful_rows),
        "num_failed_rows": len(aligned_rows) - len(successful_rows),
        "spearman": round(compute_spearman(human_scores, ai_scores), 6)
        if successful_rows
        else None,
        "exact_agreement": round(compute_exact_agreement(human_scores, ai_scores), 6)
        if successful_rows
        else None,
    }


def run_validation_benchmark(
    *,
    benchmark: str,
    dataset_path: str | Path,
    output_dir: str | Path,
    grader: Grader,
) -> dict[str, Any]:
    """Run one validation benchmark and write artifacts."""
    rows = load_validation_rows(dataset_path)
    fetcher = ValidationFetcher(rows)
    grader.fetcher = fetcher
    queries = list(dict.fromkeys(row.query for row in rows))

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    raw_judgments_path = output_root / f"{benchmark}-raw-judgments.json"
    failed_path = output_root / f"{benchmark}-failures.json"

    results = grader.grade(
        queries=queries,
        output_path=raw_judgments_path,
        output_format="json",
        failed_log_path=failed_path,
    )

    aligned_rows = align_judgments(rows, results, grader.last_failures)
    metrics = compute_metrics(aligned_rows)
    status = "completed"
    if benchmark != "smoke" and metrics["num_failed_rows"] > 0:
        status = "failed"

    summary = {
        "status": status,
        "benchmark": benchmark,
        "dataset_path": str(Path(dataset_path)),
        "raw_judgments_path": str(raw_judgments_path),
        "failures_path": str(failed_path),
        "model": grader.llm_model,
        "base_url": grader.llm_base_url,
        "passes": grader.passes,
        "workers": grader.max_workers,
        "metrics": metrics,
    }
    return {"summary": summary, "aligned_rows": aligned_rows}
