"""Resume helpers for incremental runs."""

from __future__ import annotations

import json
from pathlib import Path


def load_completed_pairs(path: str | Path) -> set[tuple[str, str]]:
    """Load already graded query/document pairs from a JSON output file."""
    output_path = Path(path)
    if not output_path.exists():
        return set()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    return {
        (str(item["query"]), str(item["doc_id"]))
        for item in payload
        if "query" in item and "doc_id" in item
    }
