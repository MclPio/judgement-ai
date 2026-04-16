from __future__ import annotations

import runpy
from pathlib import Path

import judgement_ai


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
