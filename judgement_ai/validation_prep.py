"""Shared helpers for deriving validation benchmark subsets."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def stratified_sample_rows(
    rows: list[dict[str, Any]],
    *,
    per_label: int,
) -> list[dict[str, Any]]:
    """Take a deterministic per-label sample using round-robin query balancing."""
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["human_score"])].append(row)

    sampled: list[dict[str, Any]] = []
    for label in sorted(grouped):
        by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in grouped[label]:
            by_query[str(row.get("query", ""))].append(row)

        ordered_queries = sorted(
            by_query,
            key=lambda query: (
                min(str(item.get("query_id", "")) for item in by_query[query]),
                query,
            ),
        )
        ordered_rows = {
            query: sorted(
                items,
                key=lambda item: (
                    int(item.get("rank", 0)),
                    str(item.get("doc_id", "")),
                ),
            )
            for query, items in by_query.items()
        }
        positions = {query: 0 for query in ordered_queries}
        label_sample: list[dict[str, Any]] = []

        while len(label_sample) < per_label:
            added_in_round = False
            for query in ordered_queries:
                position = positions[query]
                query_rows = ordered_rows[query]
                if position >= len(query_rows):
                    continue
                label_sample.append(query_rows[position])
                positions[query] += 1
                added_in_round = True
                if len(label_sample) >= per_label:
                    break
            if not added_in_round:
                break

        sampled.extend(label_sample)
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


def build_benchmark_report(
    candidate_rows: list[dict[str, Any]],
    benchmark_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic report describing the derived benchmark slice."""
    query_counts = Counter(str(row.get("query", "")) for row in benchmark_rows)
    candidate_fields, candidate_blankish = _field_stats(candidate_rows)
    benchmark_fields, benchmark_blankish = _field_stats(benchmark_rows)
    return {
        "candidate_total_rows": len(candidate_rows),
        "benchmark_total_rows": len(benchmark_rows),
        "candidate_label_counts": label_counts(candidate_rows),
        "benchmark_label_counts": label_counts(benchmark_rows),
        "candidate_unique_queries": len({str(row.get("query", "")) for row in candidate_rows}),
        "benchmark_unique_queries": len({str(row.get("query", "")) for row in benchmark_rows}),
        "top_query_frequencies": [
            {"query": query, "count": count}
            for query, count in query_counts.most_common(20)
        ],
        "candidate_field_counts": candidate_fields,
        "candidate_blankish_counts": candidate_blankish,
        "benchmark_field_counts": benchmark_fields,
        "benchmark_blankish_counts": benchmark_blankish,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    """Write the benchmark derivation report."""
    Path(path).write_text(json.dumps(report, indent=2), encoding="utf-8")


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


def _field_stats(rows: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    """Count field coverage and blank-like values for benchmark fields."""
    present = Counter()
    blankish = Counter()
    for row in rows:
        fields = row.get("fields", {})
        if not isinstance(fields, dict):
            continue
        for key in ["title", "brand", "description"]:
            if key in fields:
                present[key] += 1
                value = fields[key]
                if value is None or str(value).strip() == "" or str(value).lower() == "nan":
                    blankish[key] += 1
    return dict(present), dict(blankish)


def load_esci_rows(path: str | Path) -> list[dict[str, str]]:
    """Load Amazon ESCI source rows from raw or pre-flattened inputs."""
    input_path = Path(path)
    if input_path.is_dir():
        return _load_esci_directory(input_path)

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

    if suffix == ".parquet":
        return _load_esci_parquet(input_path)

    raise ValueError("Amazon ESCI input must be a directory, .csv, .jsonl, or .parquet file.")


def _load_esci_directory(directory: Path) -> list[dict[str, str]]:
    examples = _find_first_existing(
        directory,
        [
            "shopping_queries_dataset_examples.parquet",
            "shopping_queries_dataset_examples.csv",
            "shopping_queries_dataset_examples.jsonl",
        ],
    )
    products = _find_first_existing(
        directory,
        [
            "shopping_queries_dataset_products.parquet",
            "shopping_queries_dataset_products.csv",
            "shopping_queries_dataset_products.jsonl",
        ],
    )
    if examples is None or products is None:
        raise ValueError(
            "ESCI directory input must contain shopping_queries_dataset_examples "
            "and shopping_queries_dataset_products in parquet, csv, or jsonl form."
        )
    return _merge_esci_examples_and_products(examples, products)


def _load_esci_parquet(path: Path) -> list[dict[str, str]]:
    if "examples" in path.name:
        sibling = path.with_name(path.name.replace("examples", "products"))
        if sibling.exists():
            return _merge_esci_examples_and_products(path, sibling)
    return _read_tabular_rows(path)


def _merge_esci_examples_and_products(
    examples_path: Path,
    products_path: Path,
) -> list[dict[str, str]]:
    example_rows = _read_tabular_rows(examples_path)
    product_rows = _read_tabular_rows(products_path)

    product_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for row in product_rows:
        product_id = row.get("product_id", "").strip()
        locale = row.get("product_locale", "").strip()
        if product_id:
            product_lookup[(locale, product_id)] = row

    merged: list[dict[str, str]] = []
    for row in example_rows:
        product_id = row.get("product_id", "").strip()
        locale = row.get("product_locale", "").strip()
        if not product_id:
            continue
        product = product_lookup.get((locale, product_id))
        if product is None:
            raise ValueError(
                "Could not resolve ESCI product metadata for "
                f"product_id={product_id!r} locale={locale!r}."
            )
        combined = dict(row)
        for key, value in product.items():
            combined.setdefault(key, value)
        merged.append(combined)
    return merged


def filter_esci_rows(
    rows: list[dict[str, str]],
    *,
    locale: str,
    reduced_task_only: bool,
) -> list[dict[str, str]]:
    """Filter ESCI rows to the desired locale and task view."""
    filtered = [
        row
        for row in rows
        if row.get("product_locale", "").strip().lower() == locale.lower()
    ]
    if reduced_task_only:
        filtered = [
            row
            for row in filtered
            if row.get("small_version", "").strip() in {"1", "1.0", "true", "True"}
        ]
    return filtered


def _read_tabular_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError("Each JSONL line must decode to an object.")
                rows.append({str(key): _stringify(value) for key, value in item.items()})
        return rows
    if suffix == ".parquet":
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - exercised manually
            raise ValueError(
                "Reading ESCI parquet files requires pandas and pyarrow. "
                "Install with `pip install -e \".[validate]\"`."
            ) from exc
        frame = pd.read_parquet(path)
        return [
            {str(key): _stringify(value) for key, value in record.items()}
            for record in frame.to_dict(orient="records")
        ]
    raise ValueError(f"Unsupported ESCI tabular format: {path.suffix}")


def _find_first_existing(directory: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)
