"""Resume helpers for incremental runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_completed_pairs(path: str | Path) -> set[tuple[str, str]]:
    """Load already graded query/document pairs from a JSON or CSV output file."""
    output_path = Path(path)
    if not output_path.exists():
        return set()

    if output_path.suffix.lower() == ".json":
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON resume file must contain a list of graded results.")
        return {
            (str(item["query"]), str(item["doc_id"]))
            for item in payload
            if isinstance(item, dict) and "query" in item and "doc_id" in item
        }

    if output_path.suffix.lower() == ".csv":
        with output_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return {
                (str(row["query"]), str(row["docid"]))
                for row in reader
                if row.get("query") and row.get("docid")
            }

    raise ValueError("Resume is supported only for .json and .csv output files.")
