"""Helpers for deriving checked-in validation subsets from upstream benchmark rows."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def stratified_sample_rows(
    rows: list[dict[str, Any]],
    *,
    per_label: int,
) -> list[dict[str, Any]]:
    """Take a deterministic per-label sample from candidate rows."""
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["human_score"])].append(row)

    sampled: list[dict[str, Any]] = []
    for label in sorted(grouped):
        label_rows = sorted(
            grouped[label],
            key=lambda item: (
                str(item.get("query_id", "")),
                str(item.get("doc_id", "")),
            ),
        )
        sampled.extend(label_rows[:per_label])
    return sampled


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive a small validation subset from raw rows."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to raw candidate rows JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the derived subset.",
    )
    parser.add_argument(
        "--per-label",
        type=int,
        default=25,
        help="Maximum number of rows to keep per human relevance label.",
    )
    args = parser.parse_args()

    rows = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("Input must be a JSON list of candidate rows.")

    sampled = stratified_sample_rows(rows, per_label=args.per_label)
    args.output.write_text(json.dumps(sampled, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
