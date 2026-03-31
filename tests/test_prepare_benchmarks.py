from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def load_module(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_amazon = load_module(
    "validate/prepare_amazon_product_search.py",
    "validate_prepare_amazon_product_search",
)
download_amazon = load_module(
    "validate/download_amazon_esci.py",
    "validate_download_amazon_esci",
)


def test_prepare_amazon_builds_expected_rows_with_locale_and_task_filters(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,rank,product_title,product_brand,"
        "product_description,product_locale,small_version\n"
        "water bottle,p1,E,5,Insulated Bottle,Hydra,Steel bottle,us,1\n"
        "water bottle,p2,E,6,Ignored Bottle,Hydra,Steel bottle,es,1\n"
        "water bottle,p3,E,7,Ignored Full,Hydra,Steel bottle,us,0\n",
        encoding="utf-8",
    )

    rows = prepare_amazon.build_candidate_rows(
        path,
        locale="us",
        reduced_task_only=True,
    )

    assert rows == [
        {
            "benchmark": "amazon_product_search",
            "query_id": "water bottle",
            "query": "water bottle",
            "doc_id": "p1",
            "rank": 5,
            "human_score": 3,
            "fields": {
                "title": "Insulated Bottle",
                "brand": "Hydra",
                "description": "Steel bottle",
            },
        }
    ] 


def test_prepare_amazon_fails_on_missing_metadata(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,product_locale,small_version\n"
        "water bottle,p1,E,us,1\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Missing judgeable product text"):
        prepare_amazon.build_candidate_rows(path)


def test_prepare_amazon_fails_when_filters_remove_all_rows(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,product_title,product_locale,small_version\n"
        "water bottle,p1,E,Insulated Bottle,es,1\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="No Amazon ESCI rows remained"):
        prepare_amazon.build_candidate_rows(path, locale="us", reduced_task_only=True)


def test_download_amazon_downloads_default_files(monkeypatch, tmp_path) -> None:
    downloaded = []

    def fake_urlretrieve(url: str, destination: Path):
        downloaded.append((url, str(destination)))
        Path(destination).write_text("x", encoding="utf-8")
        return destination, None

    monkeypatch.setattr(download_amazon, "urlretrieve", fake_urlretrieve)

    files = download_amazon.download_esci_data(tmp_path)

    assert len(files) == 2
    assert any("shopping_queries_dataset_examples.parquet" in item[1] for item in downloaded)
    assert any("shopping_queries_dataset_products.parquet" in item[1] for item in downloaded)


def test_prepare_amazon_main_writes_benchmark_calibration_and_report(monkeypatch, tmp_path) -> None:
    source_path = tmp_path / "esci.csv"
    source_path.write_text(
        "query,product_id,esci_label,rank,product_title,product_brand,product_description,"
        "product_locale,small_version\n"
        "water bottle,p1,E,1,Insulated Bottle,Hydra,Steel bottle,us,1\n"
        "water bottle,p2,S,2,Plastic Bottle,Hydra,Daily bottle,us,1\n"
        "mug,p3,C,1,Cup Warmer,HeatCo,Warming plate,us,1\n"
        "mug,p4,I,2,Garden Hose,FlowCo,Outdoor hose,us,1\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "amazon_product_search.json"
    calibration_path = tmp_path / "amazon_product_search_calibration.json"
    report_path = tmp_path / "amazon_product_search_report.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare_amazon_product_search.py",
            "--input",
            str(source_path),
            "--output",
            str(output_path),
            "--calibration-output",
            str(calibration_path),
            "--report-output",
            str(report_path),
            "--per-label",
            "1",
            "--calibration-per-label",
            "1",
        ],
    )

    prepare_amazon.main()

    benchmark_payload = json.loads(output_path.read_text(encoding="utf-8"))
    calibration_payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    report_payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert len(benchmark_payload) == 4
    assert all(item["benchmark"] == "amazon_product_search" for item in benchmark_payload)
    assert len(calibration_payload) == 4
    assert all(
        item["benchmark"] == "amazon_product_search_calibration"
        for item in calibration_payload
    )
    assert report_payload["candidate_total_rows"] == 4
