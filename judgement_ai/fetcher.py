"""Search result fetchers and normalization helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(slots=True)
class SearchResult:
    """A single retrieved result for a query."""

    doc_id: str
    rank: int
    fields: dict[str, Any]


class ResultsFetcher(Protocol):
    """Interface implemented by result fetchers."""

    def fetch(self, query: str) -> list[SearchResult]:
        """Return results for a query."""


def normalize_result(item: Mapping[str, Any], *, default_rank: int) -> SearchResult:
    """Convert an input record into the shared SearchResult shape."""
    if "doc_id" not in item:
        raise ValueError("Each result item must include a 'doc_id'.")

    fields = item.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("'fields' must be an object when provided.")

    rank = item.get("rank", default_rank)
    return SearchResult(
        doc_id=str(item["doc_id"]),
        rank=int(rank),
        fields=fields,
    )


NormalizedResults = dict[str, list[SearchResult]]
RawResultItem = Mapping[str, Any] | SearchResult
RawResultsMapping = Mapping[str, Sequence[RawResultItem]]


def normalize_results_mapping(
    payload: Any,
    *,
    source_name: str = "Results payload",
) -> NormalizedResults:
    """Validate and normalize a query-to-results mapping."""
    if not isinstance(payload, Mapping):
        raise ValueError(
            f"{source_name} must be a JSON object that maps each query to a list of results."
        )

    normalized: NormalizedResults = {}
    for query, items in payload.items():
        if not isinstance(query, str):
            raise ValueError(f"{source_name} query keys must be strings.")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
            raise ValueError(
                f"Results in {source_name} for query {query!r} must be a list of results."
            )

        normalized_items: list[SearchResult] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, SearchResult):
                normalized_items.append(item)
                continue
            if not isinstance(item, Mapping):
                raise ValueError(
                    f"Each result in {source_name} for query {query!r} must be an object."
                )
            normalized_items.append(normalize_result(item, default_rank=index))
        normalized[query] = normalized_items

    return normalized


class InMemoryResultsFetcher:
    """Read results from an in-memory query-to-results mapping."""

    def __init__(self, payload: RawResultsMapping) -> None:
        self._payload = normalize_results_mapping(payload, source_name="In-memory results")

    def fetch(self, query: str) -> list[SearchResult]:
        """Return results matching the given query from memory."""
        return list(self._payload.get(query, []))


class FileResultsFetcher:
    """Load pre-fetched results from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._payload: NormalizedResults | None = None

    def fetch(self, query: str) -> list[SearchResult]:
        """Return results matching the given query from the input file."""
        payload = self._load_payload()
        return list(payload.get(query, []))

    def _load_payload(self) -> NormalizedResults:
        """Load and validate the input payload once."""
        if self._payload is not None:
            return self._payload

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            msg = f"Results file {self.path} was not valid JSON: {exc}"
            raise ValueError(msg) from exc

        self._payload = normalize_results_mapping(
            payload,
            source_name=f"Results file {self.path}",
        )
        return self._payload
