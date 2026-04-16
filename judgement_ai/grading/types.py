"""Shared grading datatypes and exceptions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from judgement_ai.models import GradeResult


@dataclass(slots=True)
class GradeFailure:
    """A failed query/document grading attempt after retries."""

    query: str
    doc_id: str
    rank: int
    failure_type: str
    error: str
    attempts: int
    raw_response: str | None = None


@dataclass(slots=True)
class GradeProgress:
    """Structured progress event emitted during grading."""

    event: str
    total: int
    completed: int
    successes: int
    failures: int
    skipped: int
    elapsed_seconds: float
    query: str | None = None
    doc_id: str | None = None
    attempts: int | None = None


class ParseError(ValueError):
    """Raised when the LLM response cannot be parsed safely."""

    def __init__(self, message: str, *, raw_response: str) -> None:
        super().__init__(message)
        self.raw_response = raw_response


class ProviderError(RuntimeError):
    """Raised when the provider request or response fails."""

    def __init__(self, message: str, *, failure_type: str) -> None:
        super().__init__(message)
        self.failure_type = failure_type


GradeItemCallback = Callable[[GradeResult | GradeFailure], None]
