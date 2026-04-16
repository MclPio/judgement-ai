"""Resume helpers for canonical raw judgments artifacts."""

from __future__ import annotations

import json
from pathlib import Path


def load_completed_pairs(path: str | Path) -> set[tuple[str, str]]:
    """Load already graded query/document pairs from canonical raw judgments JSON."""
    output_path = Path(path)
    if not output_path.exists():
        return set()

    if output_path.suffix.lower() != ".json":
        raise ValueError("Resume is supported only for canonical raw judgments JSON files.")

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("JSON resume file must contain a list of graded results.")
    return {
        (str(item["query"]), str(item["doc_id"]))
        for item in payload
        if isinstance(item, dict) and "query" in item and "doc_id" in item
    }
