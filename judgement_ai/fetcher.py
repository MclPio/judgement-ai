"""Search result fetchers and normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


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


class ElasticsearchFetcher:
    """Fetch top-N results from an Elasticsearch endpoint."""

    def __init__(self, url: str, top_n: int = 10, timeout: float = 30.0) -> None:
        self.url = url.rstrip("/")
        self.top_n = top_n
        self.timeout = timeout

    def fetch(self, query: str) -> list[SearchResult]:
        """Fetch results for a query from Elasticsearch."""
        try:
            response = requests.get(
                f"{self.url}/_search",
                params={"size": self.top_n, "q": query},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except (requests.RequestException, OSError, RuntimeError) as exc:
            msg = f"Failed to fetch results from Elasticsearch for query {query!r}: {exc}"
            raise RuntimeError(msg) from exc

        payload = response.json()
        hits = payload.get("hits", {}).get("hits", [])
        return [
            normalize_result(
                {
                    "doc_id": hit.get("_id", ""),
                    "rank": index,
                    "fields": hit.get("_source", {}),
                },
                default_rank=index,
            )
            for index, hit in enumerate(hits, start=1)
        ]


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

        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, dict):
            raise ValueError(
                "Results file must be a JSON object that maps each query to a list of results."
            )

        for query, items in payload.items():
            if not isinstance(query, str):
                raise ValueError("Results file query keys must be strings.")
            if not isinstance(items, list):
                raise ValueError(
                    f"Results for query {query!r} must be a list of result objects."
                )
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"Each result for query {query!r} must be a JSON object."
                    )

        self._payload = payload
        return payload
