"""Writers and export helpers for judgement lists."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

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


def write_csv_export(results: Iterable[GradeResult], path: str | Path) -> None:
    """Write results in CSV format."""
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


class ResultsWriter(Protocol):
    """Interface implemented by runtime result writers."""

    def append(self, result: GradeResult) -> None:
        """Persist one completed result."""


class JsonResultsWriter:
    """Persist JSON results incrementally as a valid JSON array."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._results = self._load_existing()

    def append(self, result: GradeResult) -> None:
        """Append one result and rewrite the JSON array via atomic replace."""
        self._results.append(result_to_dict(result))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._results, indent=2)
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = handle.name
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None and os.path.exists(temp_path):
                os.unlink(temp_path)

    def _load_existing(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON output file must contain a list of graded results.")
        return payload
