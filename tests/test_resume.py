import json

from judgement_ai.resume import load_completed_pairs


def test_load_completed_pairs_returns_existing_query_doc_pairs(tmp_path) -> None:
    output_path = tmp_path / "judgments.json"
    output_path.write_text(
        json.dumps(
            [
                {"query": "vitamin b6", "doc_id": "123"},
                {"query": "magnesium for sleep", "doc_id": "456"},
            ]
        ),
        encoding="utf-8",
    )

    pairs = load_completed_pairs(output_path)

    assert ("vitamin b6", "123") in pairs
    assert ("magnesium for sleep", "456") in pairs


def test_load_completed_pairs_supports_quepid_csv(tmp_path) -> None:
    output_path = tmp_path / "judgments.csv"
    output_path.write_text(
        "query,docid,rating\nvitamin b6,123,3\nmagnesium for sleep,456,2\n",
        encoding="utf-8",
    )

    pairs = load_completed_pairs(output_path)

    assert ("vitamin b6", "123") in pairs
    assert ("magnesium for sleep", "456") in pairs
