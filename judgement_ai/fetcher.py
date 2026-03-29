"""Search result fetcher interfaces and placeholders."""

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


class ElasticsearchFetcher:
    """Fetch top-N results from an Elasticsearch endpoint."""

    def __init__(self, url: str, top_n: int = 10, timeout: float = 30.0) -> None:
        self.url = url.rstrip("/")
        self.top_n = top_n
        self.timeout = timeout

    def fetch(self, query: str) -> list[SearchResult]:
        """Fetch results for a query from Elasticsearch."""
        response = requests.get(
            f"{self.url}/_search",
            params={"size": self.top_n, "q": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", {}).get("hits", [])
        return [
            SearchResult(
                doc_id=str(hit.get("_id", "")),
                rank=index,
                fields=hit.get("_source", {}),
            )
            for index, hit in enumerate(hits, start=1)
        ]


class FileResultsFetcher:
    """Load pre-fetched results from a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def fetch(self, query: str) -> list[SearchResult]:
        """Return results matching the given query from the input file."""
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        items = payload.get(query, [])
        return [
            SearchResult(
                doc_id=str(item["doc_id"]),
                rank=int(item.get("rank", index)),
                fields=item.get("fields", {}),
            )
            for index, item in enumerate(items, start=1)
        ]
