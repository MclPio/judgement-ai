"""Output helpers for judgement lists."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from judgement_ai.grader import GradeResult


def write_quepid_csv(results: Iterable[GradeResult], path: str | Path) -> None:
    """Write results in Quepid-compatible CSV format."""
    output_path = Path(path)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query", "docid", "rating"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "query": result.query,
                    "docid": result.doc_id,
                    "rating": result.score,
                }
            )


def write_json(results: Iterable[GradeResult], path: str | Path) -> None:
    """Write results in JSON format."""
    payload = [
        {
            "query": result.query,
            "doc_id": result.doc_id,
            "score": result.score,
            "reasoning": result.reasoning,
            "rank": result.rank,
            **({"pass_scores": result.pass_scores} if result.pass_scores else {}),
        }
        for result in results
    ]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
