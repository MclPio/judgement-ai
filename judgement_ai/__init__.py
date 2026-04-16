"""Public package interface for judgement-ai."""

from importlib.metadata import PackageNotFoundError, version

from judgement_ai.fetcher import FileResultsFetcher, InMemoryResultsFetcher, ResultsFetcher
from judgement_ai.grading import Grader
from judgement_ai.models import GradeResult

try:
    __version__ = version("judgement-ai")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "FileResultsFetcher",
    "GradeResult",
    "Grader",
    "InMemoryResultsFetcher",
    "ResultsFetcher",
    "__version__",
]
