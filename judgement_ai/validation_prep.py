"""Shared helpers for deriving validation benchmark subsets."""

from __future__ import annotations

import csv
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


def label_counts(rows: list[dict[str, Any]]) -> dict[int, int]:
    """Count rows per human label."""
    counts: dict[int, int] = defaultdict(int)
    for row in rows:
        counts[int(row["human_score"])] += 1
    return dict(sorted(counts.items()))


def write_dataset(rows: list[dict[str, Any]], path: str | Path) -> None:
    """Write the final benchmark dataset JSON."""
    Path(path).write_text(json.dumps(rows, indent=2), encoding="utf-8")


def print_summary(
    *,
    total_candidates: int,
    before_counts: dict[int, int],
    after_counts: dict[int, int],
    final_rows: int,
    output_path: str | Path | None,
    dry_run: bool,
) -> None:
    """Print a standard derivation summary."""
    print(f"Total candidate rows: {total_candidates}")
    print(f"Per-label counts before sampling: {before_counts}")
    print(f"Per-label counts after sampling: {after_counts}")
    print(f"Final row count: {final_rows}")
    if dry_run:
        print("Dry run: no dataset file was written.")
    elif output_path is not None:
        print(f"Output path: {output_path}")


def load_esci_rows(path: str | Path) -> list[dict[str, str]]:
    """Load Amazon ESCI source rows from CSV or JSONL."""
    input_path = Path(path)
    suffix = input_path.suffix.lower()

    if suffix == ".csv":
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    if suffix == ".jsonl":
        rows: list[dict[str, str]] = []
        with input_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError("Each JSONL line must decode to an object.")
                rows.append({str(key): _stringify(value) for key, value in item.items()})
        return rows

    raise ValueError("Amazon ESCI input must be a .csv or .jsonl file.")


def _stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)
