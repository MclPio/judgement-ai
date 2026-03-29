"""Prompt helpers and validation."""

from __future__ import annotations

from pathlib import Path

REQUIRED_PROMPT_FIELDS = {"query", "result_fields", "scale_labels"}
OPTIONAL_PROMPT_FIELDS = {"domain_context"}

DEFAULT_PROMPT_TEMPLATE = """You are a search relevance expert.
{domain_context}

Your task is to grade how relevant the following search result is to the query.

Use this scale:
{scale_labels}

First, write 2-3 sentences explaining your reasoning.
Then output your score on a new line in exactly this format:
SCORE: <number>

Query: {query}

Result:
{result_fields}

Reasoning:
"""


def load_prompt_template(path: str | Path | None = None) -> str:
    """Return the default prompt or load a custom template from disk."""
    if path is None:
        return DEFAULT_PROMPT_TEMPLATE
    return Path(path).read_text(encoding="utf-8")


def validate_prompt_template(template: str) -> None:
    """Ensure required placeholders exist before grading begins."""
    missing = [
        field for field in REQUIRED_PROMPT_FIELDS if f"{{{field}}}" not in template
    ]
    if missing:
        msg = f"Prompt template is missing required placeholders: {', '.join(sorted(missing))}"
        raise ValueError(msg)

