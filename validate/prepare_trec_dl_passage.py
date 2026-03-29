"""Derive the canonical TREC DL passage validation subset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judgement_ai.validation_prep import (  # noqa: E402
    label_counts,
    print_summary,
    stratified_sample_rows,
    write_dataset,
)


def build_candidate_rows(dataset_id: str) -> list[dict[str, object]]:
    """Load candidate rows from ir-datasets."""
    try:
        import ir_datasets
    except ImportError as exc:  # pragma: no cover - exercised manually
        raise SystemExit(
            "ir-datasets is required for TREC DL derivation. "
            "Install with `pip install -e \".[validate]\"`."
        ) from exc

    dataset = ir_datasets.load(dataset_id)
    query_lookup = {query.query_id: query.text for query in dataset.queries_iter()}

    if not query_lookup:
        raise SystemExit(f"No queries found for dataset {dataset_id!r}.")

    if not hasattr(dataset, "docs_store"):
        raise SystemExit(f"Dataset {dataset_id!r} does not expose docs_store().")
    docs_store = dataset.docs_store()

    doc_rank_lookup: dict[tuple[str, str], int] = {}
    if hasattr(dataset, "scoreddocs_iter"):
        try:
            for scored in dataset.scoreddocs_iter():
                doc_rank_lookup[(str(scored.query_id), str(scored.doc_id))] = int(
                    getattr(scored, "rank", 0)
                )
        except Exception:
            doc_rank_lookup = {}

    rows: list[dict[str, object]] = []
    source_order_by_query: dict[str, int] = {}
    for qrel in dataset.qrels_iter():
        query_id = str(qrel.query_id)
        doc_id = str(qrel.doc_id)
        if query_id not in query_lookup:
            raise SystemExit(f"Missing query text for query_id={query_id}.")

        doc = docs_store.get(doc_id)
        if doc is None:
            raise SystemExit(f"Could not resolve passage text for doc_id={doc_id}.")

        passage_text = _resolve_passage_text(doc)
        if not passage_text:
            raise SystemExit(f"Resolved empty passage text for doc_id={doc_id}.")

        source_order_by_query[query_id] = source_order_by_query.get(query_id, 0) + 1
        rank = doc_rank_lookup.get((query_id, doc_id), source_order_by_query[query_id])

        rows.append(
            {
                "benchmark": "trec_dl_passage",
                "query_id": query_id,
                "query": query_lookup[query_id],
                "doc_id": doc_id,
                "rank": rank,
                "human_score": int(qrel.relevance),
                "fields": {"passage_text": passage_text},
            }
        )
    return rows


def _resolve_passage_text(doc: object) -> str:
    for field in ("text", "body", "contents"):
        value = getattr(doc, field, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive the canonical TREC DL passage validation subset."
    )
    parser.add_argument(
        "--dataset-id",
        default="msmarco-passage/trec-dl-2019/judged",
        help="ir-datasets identifier to load.",
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
        default=Path(__file__).with_name("datasets") / "trec_dl_passage.json",
        help="Path to write the final dataset JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only without writing the dataset file.",
    )
    args = parser.parse_args()

    rows = build_candidate_rows(args.dataset_id)
    sampled = stratified_sample_rows(rows, per_label=args.per_label)
    before_counts = label_counts(rows)
    after_counts = label_counts(sampled)

    if not args.dry_run:
        write_dataset(sampled, args.output)

    print_summary(
        total_candidates=len(rows),
        before_counts=before_counts,
        after_counts=after_counts,
        final_rows=len(sampled),
        output_path=args.output,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
