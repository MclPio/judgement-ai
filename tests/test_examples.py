from __future__ import annotations

import runpy
from pathlib import Path

import judgement_ai
from judgement_ai.config import load_config
from judgement_ai.fetcher import FileResultsFetcher


class DummyFetcher:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class DummyGrader:
    last_init_kwargs: dict[str, object] | None = None
    last_grade_kwargs: dict[str, object] | None = None

    def __init__(self, **kwargs) -> None:
        type(self).last_init_kwargs = kwargs

    def grade(self, **kwargs):
        type(self).last_grade_kwargs = kwargs
        return []


def _run_example(monkeypatch, relative_path: str) -> tuple[dict[str, object], dict[str, object]]:
    monkeypatch.setattr(judgement_ai, "FileResultsFetcher", DummyFetcher)
    monkeypatch.setattr(judgement_ai, "InMemoryResultsFetcher", DummyFetcher)
    monkeypatch.setattr(judgement_ai, "Grader", DummyGrader)
    DummyGrader.last_init_kwargs = None
    DummyGrader.last_grade_kwargs = None

    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / relative_path),
        run_name="__main__",
    )

    assert DummyGrader.last_init_kwargs is not None
    assert DummyGrader.last_grade_kwargs is not None
    return DummyGrader.last_init_kwargs, DummyGrader.last_grade_kwargs


def test_ollama_example_uses_supported_grader_arguments(monkeypatch) -> None:
    init_kwargs, grade_kwargs = _run_example(monkeypatch, "examples/ollama_example.py")

    assert init_kwargs["provider"] == "ollama"
    assert init_kwargs["max_attempts"] == 1
    assert "max_retries" not in init_kwargs
    assert grade_kwargs["queries"] == ["vitamin b6"]


def test_example_configs_load() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    openai_config = load_config(repo_root / "examples/openai-config.yaml")
    ollama_config = load_config(repo_root / "examples/ollama-config.yaml")

    assert openai_config["queries"] == "examples/queries.txt"
    assert openai_config["search"]["results_file"] == "examples/results.json"
    assert ollama_config["llm"]["provider"] == "ollama"
    assert ollama_config["grading"]["response_mode"] == "json_schema"


def test_example_results_json_is_loadable() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fetcher = FileResultsFetcher(repo_root / "examples/results.json")

    vitamin_results = fetcher.fetch("vitamin b6")
    magnesium_results = fetcher.fetch("magnesium for sleep")

    assert [item.doc_id for item in vitamin_results] == ["vit-b6-100mg", "b-complex"]
    assert [item.doc_id for item in magnesium_results] == ["mag-glycinate", "melatonin"]
