"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GradeResult:
    """A graded query/document pair."""

    query: str
    doc_id: str
    score: int
    reasoning: str
    rank: int
    pass_scores: list[int] = field(default_factory=list)
