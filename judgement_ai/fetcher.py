"""Search result fetchers and normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SearchResult:
    """A single retrieved result for a query."""

    doc_id: str
    rank: int
    fields: dict[str, Any]


def normalize_result(item: dict[str, Any], *, default_rank: int) -> SearchResult:
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


class FileResultsFetcher:
    """Load pre-fetched results from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._payload: dict[str, list[dict[str, Any]]] | None = None

    def fetch(self, query: str) -> list[SearchResult]:
        """Return results matching the given query from the input file."""
        payload = self._load_payload()
        items = payload.get(query, [])
        return [
            normalize_result(item, default_rank=index)
            for index, item in enumerate(items, start=1)
        ]

    def _load_payload(self) -> dict[str, list[dict[str, Any]]]:
        """Load and validate the input payload once."""
        if self._payload is not None:
            return self._payload

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            msg = f"Results file {self.path} was not valid JSON: {exc}"
            raise ValueError(msg) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"Results file {self.path} must be a JSON object that maps each query to a list "
                "of results."
            )

        for query, items in payload.items():
            if not isinstance(query, str):
                raise ValueError(f"Results file {self.path} query keys must be strings.")
            if not isinstance(items, list):
                raise ValueError(
                    f"Results in {self.path} for query {query!r} must be a list of result objects."
                )
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"Each result in {self.path} for query {query!r} must be a JSON object."
                    )

        self._payload = payload
        return payload
