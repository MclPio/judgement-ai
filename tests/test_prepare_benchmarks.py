from __future__ import annotations

import importlib.util
import sys

import pytest


def load_module(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_trec_dl = load_module(
    "validate/prepare_trec_dl_passage.py",
    "validate_prepare_trec_dl_passage",
)
prepare_product = load_module(
    "validate/prepare_trec_product_search.py",
    "validate_prepare_trec_product_search",
)


class FakeQuery:
    def __init__(self, query_id: str, text: str) -> None:
        self.query_id = query_id
        self.text = text


class FakeQrel:
    def __init__(self, query_id: str, doc_id: str, relevance: int) -> None:
        self.query_id = query_id
        self.doc_id = doc_id
        self.relevance = relevance


class FakeScoredDoc:
    def __init__(self, query_id: str, doc_id: str, rank: int) -> None:
        self.query_id = query_id
        self.doc_id = doc_id
        self.rank = rank


class FakeDoc:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeDocsStore:
    def __init__(self, docs: dict[str, FakeDoc]) -> None:
        self.docs = docs

    def get(self, doc_id: str):
        return self.docs.get(doc_id)


class FakeIrDataset:
    def queries_iter(self):
        return iter([FakeQuery("q1", "vitamin b6")])

    def qrels_iter(self):
        return iter([FakeQrel("q1", "d1", 3)])

    def scoreddocs_iter(self):
        return iter([FakeScoredDoc("q1", "d1", 7)])

    def docs_store(self):
        return FakeDocsStore({"d1": FakeDoc("Vitamin B6 passage text")})


def test_prepare_trec_dl_builds_expected_rows(monkeypatch) -> None:
    class FakeIrDatasetsModule:
        @staticmethod
        def load(dataset_id: str):
            assert dataset_id == "msmarco-passage/trec-dl-2019/judged"
            return FakeIrDataset()

    monkeypatch.setitem(sys.modules, "ir_datasets", FakeIrDatasetsModule())

    rows = prepare_trec_dl.build_candidate_rows("msmarco-passage/trec-dl-2019/judged")

    assert rows == [
        {
            "benchmark": "trec_dl_passage",
            "query_id": "q1",
            "query": "vitamin b6",
            "doc_id": "d1",
            "rank": 7,
            "human_score": 3,
            "fields": {"passage_text": "Vitamin B6 passage text"},
        }
    ]


def test_prepare_trec_dl_fails_on_missing_text(monkeypatch) -> None:
    class BrokenDataset(FakeIrDataset):
        def docs_store(self):
            return FakeDocsStore({"d1": FakeDoc("")})

    class FakeIrDatasetsModule:
        @staticmethod
        def load(dataset_id: str):
            del dataset_id
            return BrokenDataset()

    monkeypatch.setitem(sys.modules, "ir_datasets", FakeIrDatasetsModule())

    with pytest.raises(SystemExit, match="empty passage text"):
        prepare_trec_dl.build_candidate_rows("msmarco-passage/trec-dl-2019/judged")


def test_prepare_product_builds_expected_rows(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label,rank,product_title,product_brand,product_description\n"
        "water bottle,p1,E,5,Insulated Bottle,Hydra,Steel bottle\n",
        encoding="utf-8",
    )

    rows = prepare_product.build_candidate_rows(path)

    assert rows == [
        {
            "benchmark": "trec_product_search",
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


def test_prepare_product_fails_on_missing_metadata(tmp_path) -> None:
    path = tmp_path / "esci.csv"
    path.write_text(
        "query,product_id,esci_label\n"
        "water bottle,p1,E\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="Missing judgeable product text"):
        prepare_product.build_candidate_rows(path)
