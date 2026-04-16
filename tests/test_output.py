import csv
import json

from judgement_ai.models import GradeResult
from judgement_ai.output import JsonResultsWriter, result_to_dict, write_csv_export


def test_result_to_dict_includes_optional_pass_scores() -> None:
    result = GradeResult(
        query="vitamin b6",
        doc_id="123",
        score=3,
        reasoning="Direct match.",
        rank=1,
        pass_scores=[3, 2, 3],
    )

    payload = result_to_dict(result)

    assert payload["doc_id"] == "123"
    assert payload["pass_scores"] == [3, 2, 3]


def test_json_results_writer_appends_valid_json(tmp_path) -> None:
    path = tmp_path / "judgments.json"
    writer = JsonResultsWriter(path)

    writer.append(
        GradeResult(
            query="vitamin b6",
            doc_id="123",
            score=3,
            reasoning="Direct match.",
            rank=1,
        )
    )
    writer.append(
        GradeResult(
            query="magnesium",
            doc_id="456",
            score=1,
            reasoning="Weak match.",
            rank=2,
        )
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [item["doc_id"] for item in payload] == ["123", "456"]
    assert [item.name for item in tmp_path.iterdir()] == ["judgments.json"]


def test_write_csv_export_writes_rows(tmp_path) -> None:
    path = tmp_path / "judgments.csv"
    write_csv_export(
        [
            GradeResult(
                query="vitamin b6",
                doc_id="123",
                score=3,
                reasoning="Direct match.",
                rank=1,
            ),
            GradeResult(
                query="magnesium",
                doc_id="456",
                score=1,
                reasoning="Weak match.",
                rank=2,
            ),
        ],
        path,
    )

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {"query": "vitamin b6", "docid": "123", "rating": "3"},
        {"query": "magnesium", "docid": "456", "rating": "1"},
    ]
