"""Derive the canonical Amazon product-search validation subset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judgement_ai.validation_prep import (  # noqa: E402
    build_benchmark_report,
    filter_esci_rows,
    label_counts,
    load_esci_rows,
    print_summary,
    stratified_sample_rows,
    write_dataset,
    write_report,
)
from validate.download_amazon_esci import download_esci_data  # noqa: E402

ESCI_LABELS = {
    "E": 3,
    "S": 2,
    "C": 1,
    "I": 0,
}


def build_candidate_rows(
    source_path: str | Path,
    *,
    locale: str = "us",
    reduced_task_only: bool = True,
    benchmark: str = "amazon_product_search",
) -> list[dict[str, object]]:
    """Load candidate rows from Amazon ESCI source data."""
    source_rows = load_esci_rows(source_path)
    if not source_rows:
        raise SystemExit("No source rows were loaded from the ESCI input file.")

    source_rows = filter_esci_rows(
        source_rows,
        locale=locale,
        reduced_task_only=reduced_task_only,
    )
    if not source_rows:
        raise SystemExit(
            "No Amazon ESCI rows remained after applying the requested locale/task filters."
        )

    query_order: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for index, row in enumerate(source_rows, start=1):
        query = _first_present(row, ["query", "query_text"])
        if not query:
            raise SystemExit(f"Missing query text in ESCI row {index}.")

        doc_id = _first_present(row, ["product_id", "doc_id", "asin"])
        if not doc_id:
            raise SystemExit(f"Missing product/document id in ESCI row {index}.")

        label = _first_present(row, ["esci_label", "label"])
        if label not in ESCI_LABELS:
            raise SystemExit(f"Unsupported ESCI label {label!r} in row {index}.")

        title = _first_present(row, ["product_title", "title"])
        description = _first_present(row, ["product_description", "description"])
        brand = _first_present(row, ["product_brand", "brand"])
        if not any([title, description, brand]):
            raise SystemExit(f"Missing judgeable product text/metadata in ESCI row {index}.")

        query_id = _first_present(row, ["query_id"]) or query
        rank_value = _first_present(row, ["rank"])
        if query not in query_order:
            query_order[query] = 0
        query_order[query] += 1
        rank = int(rank_value) if rank_value else query_order[query]

        fields = {}
        if title:
            fields["title"] = title
        if brand:
            fields["brand"] = brand
        if description:
            fields["description"] = description

        rows.append(
            {
                "benchmark": benchmark,
                "query_id": str(query_id),
                "query": query,
                "doc_id": doc_id,
                "rank": rank,
                "human_score": ESCI_LABELS[label],
                "fields": fields,
            }
        )
    return rows


def _first_present(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key, "")
        if value and value.strip():
            return value.strip()
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and derive the canonical Amazon product-search validation subset."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).with_name("data") / "amazon_esci",
        help="Path to the ESCI data directory, examples parquet, or flat CSV/JSONL source file.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=(
            "Download the official Amazon ESCI source files into the input "
            "directory before deriving."
        ),
    )
    parser.add_argument(
        "--locale",
        default="us",
        help="Locale to keep from the Amazon ESCI data.",
    )
    parser.add_argument(
        "--full-task",
        action="store_true",
        help="Use the full task data instead of the reduced Task 1 slice.",
    )
    parser.add_argument(
        "--per-label",
        type=int,
        default=50,
        help="Maximum number of rows to keep per human relevance label.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("data") / "amazon_product_search.json",
        help="Path to write the final dataset JSON.",
    )
    parser.add_argument(
        "--calibration-output",
        type=Path,
        default=Path(__file__).with_name("data") / "amazon_product_search_calibration.json",
        help="Path to write the fixed-size calibration dataset JSON.",
    )
    parser.add_argument(
        "--calibration-per-label",
        type=int,
        default=12,
        help="Maximum number of rows to keep per label in the calibration slice.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(__file__).with_name("data") / "amazon_product_search_report.json",
        help="Path to write the derivation report JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only without writing the dataset file.",
    )
    args = parser.parse_args()

    source_path = args.input
    if args.download:
        download_esci_data(source_path)

    rows = build_candidate_rows(
        source_path,
        locale=args.locale,
        reduced_task_only=not args.full_task,
    )
    sampled = stratified_sample_rows(rows, per_label=args.per_label)
    calibration = [
        {**row, "benchmark": "amazon_product_search_calibration"}
        for row in stratified_sample_rows(rows, per_label=args.calibration_per_label)
    ]
    report = build_benchmark_report(rows, sampled)
    before_counts = label_counts(rows)
    after_counts = label_counts(sampled)

    if not args.dry_run:
        write_dataset(sampled, args.output)
        write_dataset(calibration, args.calibration_output)
        write_report(report, args.report_output)

    print_summary(
        total_candidates=len(rows),
        before_counts=before_counts,
        after_counts=after_counts,
        final_rows=len(sampled),
        output_path=args.output,
        dry_run=args.dry_run,
    )
    print(f"Calibration row count: {len(calibration)}")
    if args.dry_run:
        print("Dry run: no calibration or report files were written.")
    else:
        print(f"Calibration output path: {args.calibration_output}")
        print(f"Report output path: {args.report_output}")


if __name__ == "__main__":
    main()
