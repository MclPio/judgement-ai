from pathlib import Path

from judgement_ai.validation_prep import label_counts, load_esci_rows, stratified_sample_rows


def test_stratified_sample_rows_is_deterministic_per_label() -> None:
    rows = [
        {"query_id": "q2", "doc_id": "b", "human_score": 1},
        {"query_id": "q1", "doc_id": "a", "human_score": 1},
        {"query_id": "q3", "doc_id": "c", "human_score": 3},
        {"query_id": "q4", "doc_id": "d", "human_score": 3},
    ]

    sampled = stratified_sample_rows(rows, per_label=1)

    assert sampled == [
        {"query_id": "q1", "doc_id": "a", "human_score": 1},
        {"query_id": "q3", "doc_id": "c", "human_score": 3},
    ]


def test_label_counts_returns_sorted_mapping() -> None:
    counts = label_counts(
        [
            {"human_score": 3},
            {"human_score": 0},
            {"human_score": 3},
        ]
    )

    assert counts == {0: 1, 3: 2}


def test_load_esci_rows_supports_csv(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,product_title\n"
        "water bottle,p1,E,Insulated Bottle\n",
        encoding="utf-8",
    )

    rows = load_esci_rows(path)

    assert rows[0]["query"] == "water bottle"
    assert rows[0]["product_id"] == "p1"


def test_provenance_files_exist() -> None:
    assert Path("validate/provenance/trec_dl_passage.md").exists()
    assert Path("validate/provenance/trec_product_search.md").exists()

