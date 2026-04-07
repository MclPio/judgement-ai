"""Helpers for loading canonical raw judgments artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from judgement_ai.models import GradeResult


def load_json_results(path: str | Path) -> list[GradeResult]:
    """Load grade results from a canonical raw judgments JSON file."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("JSON results file must contain a list of graded results.")

    results: list[GradeResult] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each JSON result entry must be an object.")
        results.append(
            GradeResult(
                query=str(item["query"]),
                doc_id=str(item["doc_id"]),
                score=int(item["score"]),
                reasoning=str(item["reasoning"]),
                rank=int(item.get("rank", 1)),
                pass_scores=[int(score) for score in item.get("pass_scores", [])],
            )
        )
    return results
