"""Core grading orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from judgement_ai.prompts import (
    DEFAULT_SCALE_LABELS,
    load_prompt_template,
    validate_prompt_template,
)


@dataclass(slots=True)
class GradeResult:
    """A graded query/document pair."""

    query: str
    doc_id: str
    score: int
    reasoning: str
    rank: int
    pass_scores: list[int] = field(default_factory=list)


class Grader:
    """Coordinate fetching, grading, and result collection."""

    def __init__(
        self,
        *,
        fetcher: Any,
        llm_base_url: str,
        llm_api_key: str | None,
        llm_model: str,
        domain_context: str | None = None,
        scale_min: int = 0,
        scale_max: int = 3,
        scale_labels: dict[int, str] | None = None,
        max_workers: int = 10,
        passes: int = 1,
        prompt_template: str | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.domain_context = domain_context or ""
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.scale_labels = scale_labels or DEFAULT_SCALE_LABELS.copy()
        self.max_workers = max_workers
        self.passes = passes
        self.prompt_template = load_prompt_template(prompt_template)
        validate_prompt_template(self.prompt_template)

    def grade(
        self,
        *,
        queries: list[str],
        resume_from: str | None = None,
    ) -> list[GradeResult]:
        """Placeholder library entrypoint for future implementation."""
        del resume_from
        results: list[GradeResult] = []
        for query in queries:
            for item in self.fetcher.fetch(query):
                results.append(
                    GradeResult(
                        query=query,
                        doc_id=item.doc_id,
                        score=self.scale_min,
                        reasoning="Not implemented yet.",
                        rank=item.rank,
                        pass_scores=[],
                    )
                )
        return results
