"""Output helpers for judgement lists."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from judgement_ai.models import GradeResult


def result_to_dict(result: GradeResult) -> dict[str, object]:
    """Convert a grade result into the JSON output shape."""
    return {
        "query": result.query,
        "doc_id": result.doc_id,
        "score": result.score,
        "reasoning": result.reasoning,
        "rank": result.rank,
        **({"pass_scores": result.pass_scores} if result.pass_scores else {}),
    }


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
    payload = [result_to_dict(result) for result in results]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


class JsonResultsWriter:
    """Persist JSON results incrementally as a valid JSON array."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._results = self._load_existing()

    def append(self, result: GradeResult) -> None:
        """Append one result and rewrite the JSON array atomically."""
        self._results.append(result_to_dict(result))
        self.path.write_text(json.dumps(self._results, indent=2), encoding="utf-8")

    def _load_existing(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON output file must contain a list of graded results.")
        return payload


class QuepidCsvWriter:
    """Append Quepid-compatible CSV rows incrementally."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.fieldnames = ["query", "docid", "rating"]
        if not self.path.exists():
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
                writer.writeheader()

    def append(self, result: GradeResult) -> None:
        """Append one result row to the CSV output."""
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fieldnames)
            writer.writerow(
                {
                    "query": result.query,
                    "docid": result.doc_id,
                    "rating": result.score,
                }
            )
