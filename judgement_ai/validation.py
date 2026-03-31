"""Validation helpers and benchmark orchestration."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from judgement_ai.fetcher import SearchResult
from judgement_ai.grader import GradeFailure, Grader
from judgement_ai.models import GradeResult
from judgement_ai.output import load_json_results


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
                        "failure_type": failure.failure_type,
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


def build_validation_analysis(aligned_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize failure patterns and score collapse signals for a benchmark run."""
    scored_rows = [row for row in aligned_rows if "ai_score" in row]
    failure_rows = [row for row in aligned_rows if "failure" in row]
    failure_types = Counter(
        str(row["failure"].get("failure_type", "unknown_error")) for row in failure_rows
    )
    parse_failures = [
        row
        for row in failure_rows
        if row["failure"].get("failure_type") == "parse_error"
    ]
    empty_raw = sum(
        1
        for row in parse_failures
        if str(row["failure"].get("raw_response", "")).strip() == ""
    )
    non_empty_raw = len(parse_failures) - empty_raw
    ai_distribution = Counter(int(row["ai_score"]) for row in scored_rows)
    failure_queries = Counter(row["query"] for row in failure_rows)
    warnings: list[str] = []
    if scored_rows:
        if len(ai_distribution) < 3:
            warnings.append("Score distribution used fewer than three labels.")
        largest_bucket = max(ai_distribution.values()) / len(scored_rows)
        if largest_bucket > 0.7:
            warnings.append("A single AI score bucket exceeded 70% of scored rows.")

    return {
        "failure_counts_by_type": dict(sorted(failure_types.items())),
        "parse_failures_empty_raw": empty_raw,
        "parse_failures_non_empty_raw": non_empty_raw,
        "ai_score_distribution": dict(sorted(ai_distribution.items())),
        "top_failure_queries": [
            {"query": query, "count": count}
            for query, count in failure_queries.most_common(15)
        ],
        "warnings": warnings,
    }


def load_failed_pairs(path: str | Path) -> set[tuple[str, str]]:
    """Load failed query/document pairs from a JSON failures file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Failures file must be a JSON list.")

    pairs: set[tuple[str, str]] = set()
    for item in payload:
        if isinstance(item, dict) and "query" in item and "doc_id" in item:
            pairs.add((str(item["query"]), str(item["doc_id"])))
    return pairs


def load_failures(path: str | Path) -> list[GradeFailure]:
    """Load persisted failure entries into GradeFailure objects."""
    file_path = Path(path)
    if not file_path.exists():
        return []

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Failures file must be a JSON list.")

    failures: list[GradeFailure] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        failures.append(
            GradeFailure(
                query=str(item["query"]),
                doc_id=str(item["doc_id"]),
                rank=int(item.get("rank", 1)),
                failure_type=str(item.get("failure_type", "unknown_error")),
                error=str(item.get("error", "Unknown grading failure.")),
                attempts=int(item.get("attempts", 1)),
                raw_response=item.get("raw_response")
                if isinstance(item.get("raw_response"), str)
                else None,
            )
        )
    return failures


def build_calibration_gate(
    *,
    benchmark: str,
    grader: Grader,
    metrics: dict[str, Any],
    analysis: dict[str, Any],
) -> dict[str, Any] | None:
    """Build calibration gate results for the calibration benchmark."""
    if benchmark != "amazon_product_search_calibration":
        return None

    track = "local" if grader.resolved_provider == "ollama" else "reference"
    ai_distribution = {
        int(score): int(count)
        for score, count in dict(analysis["ai_score_distribution"]).items()
    }
    num_scored = int(metrics["num_scored_rows"])
    max_bucket_share = (
        max(ai_distribution.values()) / num_scored if num_scored and ai_distribution else 0.0
    )
    labels_used = len(ai_distribution)
    failure_counts = dict(analysis["failure_counts_by_type"])
    total_failures = int(metrics["num_failed_rows"])
    total_rows = int(metrics["num_rows"])

    checks: dict[str, bool] = {
        "no_timeout_failures": int(failure_counts.get("timeout", 0)) == 0,
        "uses_at_least_three_labels": labels_used >= 3,
        "no_score_collapse": max_bucket_share <= 0.7,
    }
    if track == "local":
        checks["failure_rate_at_most_5_percent"] = total_failures <= max(0, total_rows * 0.05)
    else:
        checks["no_parse_failures"] = int(failure_counts.get("parse_error", 0)) == 0
        checks["spearman_at_least_0_40"] = (metrics["spearman"] or 0.0) >= 0.4

    failed_reasons = [name for name, passed in checks.items() if not passed]
    warnings: list[str] = []
    if track == "reference":
        spearman = metrics["spearman"] or 0.0
        if 0.4 <= spearman < 0.6:
            warnings.append(
                "Reference calibration is viable enough to continue, "
                "but the thesis remains uncertain."
            )
        elif spearman >= 0.6:
            warnings.append(
                "Reference calibration cleared the confidence threshold for the fast thesis test."
            )

    return {
        "benchmark": benchmark,
        "track": track,
        "passed": all(checks.values()),
        "checks": checks,
        "failed_reasons": failed_reasons,
        "warnings": warnings,
        "metrics": metrics,
        "analysis": analysis,
    }


def run_validation_benchmark(
    *,
    benchmark: str,
    dataset_path: str | Path,
    output_dir: str | Path,
    grader: Grader,
    resume: bool = False,
    retry_failures_from: str | Path | None = None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """Run one validation benchmark and write artifacts."""
    all_rows = load_validation_rows(dataset_path)
    rows = all_rows
    if retry_failures_from is not None:
        failed_pairs = load_failed_pairs(retry_failures_from)
        rows = [row for row in all_rows if (row.query, row.doc_id) in failed_pairs]

    fetcher = ValidationFetcher(rows)
    grader.fetcher = fetcher
    queries = list(dict.fromkeys(row.query for row in rows))

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    raw_judgments_path = output_root / f"{benchmark}-raw-judgments.json"
    failed_path = output_root / f"{benchmark}-failures.json"
    aligned_path = output_root / f"{benchmark}-aligned.json"
    summary_path = output_root / f"{benchmark}-summary.json"
    analysis_path = output_root / f"{benchmark}-analysis.json"

    if retry_failures_from is not None and not raw_judgments_path.exists():
        raise ValueError(
            "Retry sweeps require an existing raw judgments file in the output directory."
        )

    current_results: dict[tuple[str, str], GradeResult] = {
        (result.query, result.doc_id): result
        for result in load_json_results(raw_judgments_path)
    } if raw_judgments_path.exists() else {}
    current_failures: dict[tuple[str, str], GradeFailure] = {
        (failure.query, failure.doc_id): failure for failure in load_failures(failed_path)
    } if (resume or retry_failures_from is not None) else {}

    def _sorted_results() -> list[GradeResult]:
        result_order = {
            (row.query, row.doc_id): index for index, row in enumerate(all_rows)
        }
        return sorted(
            current_results.values(),
            key=lambda item: result_order.get((item.query, item.doc_id), 10**9),
        )

    def _sorted_failures() -> list[GradeFailure]:
        failure_order = {
            (row.query, row.doc_id): index for index, row in enumerate(all_rows)
        }
        return sorted(
            current_failures.values(),
            key=lambda item: failure_order.get((item.query, item.doc_id), 10**9),
        )

    def _write_state(status: str) -> dict[str, Any]:
        aligned_rows = align_judgments(all_rows, _sorted_results(), _sorted_failures())
        metrics = compute_metrics(aligned_rows)
        analysis = build_validation_analysis(aligned_rows)
        summary = {
            "status": status,
            "benchmark": benchmark,
            "dataset_path": str(Path(dataset_path)),
            "raw_judgments_path": str(raw_judgments_path),
            "failures_path": str(failed_path),
            "aligned_path": str(aligned_path),
            "analysis_path": str(analysis_path),
            "model": grader.llm_model,
            "base_url": grader.llm_base_url,
            "provider": grader.resolved_provider,
            "response_mode": grader.response_mode,
            "temperature": grader.temperature,
            "passes": grader.passes,
            "workers": grader.max_workers,
            "request_timeout": grader.request_timeout,
            "max_retries": grader.max_retries,
            "resume": resume,
            "retry_failures_from": str(retry_failures_from) if retry_failures_from else None,
            "metrics": metrics,
        }
        gate = build_calibration_gate(
            benchmark=benchmark,
            grader=grader,
            metrics=metrics,
            analysis=analysis,
        )
        if gate is not None:
            gate_path = output_root / f"{benchmark}-{gate['track']}-gate.json"
            summary["gate_path"] = str(gate_path)
            gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")

        aligned_path.write_text(json.dumps(aligned_rows, indent=2), encoding="utf-8")
        analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {"summary": summary, "aligned_rows": aligned_rows, "analysis": analysis}

    _write_state("running")

    def _on_item(item: GradeResult | GradeFailure) -> None:
        if isinstance(item, GradeResult):
            current_results[(item.query, item.doc_id)] = item
            current_failures.pop((item.query, item.doc_id), None)
        else:
            current_failures[(item.query, item.doc_id)] = item
            current_results.pop((item.query, item.doc_id), None)
        _write_state("running")

    grader.grade(
        queries=queries,
        resume_from=raw_judgments_path if (resume or retry_failures_from is not None) else None,
        output_path=raw_judgments_path,
        output_format="json",
        failed_log_path=failed_path,
        progress_callback=progress_callback,
        item_callback=_on_item,
    )

    current_results = {
        (result.query, result.doc_id): result for result in load_json_results(raw_judgments_path)
    } if raw_judgments_path.exists() else {}
    current_failures = {
        (failure.query, failure.doc_id): failure for failure in grader.last_failures
    }

    final_state = _write_state("completed")
    if benchmark != "smoke" and final_state["summary"]["metrics"]["num_failed_rows"] > 0:
        final_state = _write_state("failed")
    return final_state
