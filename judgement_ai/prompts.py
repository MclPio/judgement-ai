"""Prompt helpers, defaults, and validation."""

from __future__ import annotations

import json
from pathlib import Path
from string import Formatter
from typing import Any

REQUIRED_PROMPT_FIELDS = {"query", "result_fields", "scale_labels"}
OPTIONAL_PROMPT_FIELDS = {"domain_context", "output_instructions"}

DEFAULT_SCALE_LABELS = {
    0: "Completely irrelevant - the result has no connection to the query.",
    1: (
        "Related but not relevant - the result shares a topic but does not address "
        "the query intent."
    ),
    2: "Relevant - the result addresses the query but is not the best possible result.",
    3: (
        "Perfectly relevant - the result directly and completely addresses the "
        "query intent."
    ),
}

DEFAULT_PROMPT_TEMPLATE = """You are a search relevance expert.
{domain_context}
Your task is to grade how relevant the following search result is to the query.

Use this scale:
{scale_labels}

{output_instructions}

Query: {query}

Result:
{result_fields}

Reasoning:
"""

DEFAULT_OUTPUT_INSTRUCTIONS = {
    "text": (
        "First, write 2-3 sentences explaining your reasoning.\n"
        "Then output your score on a new line in exactly this format:\n"
        "SCORE: <number>"
    ),
    "json_schema": (
        "Respond with a JSON object matching the required schema.\n"
        "Use a concise reasoning string and an integer score from the provided scale."
    ),
}

def load_prompt_template(path: str | Path | None = None) -> str:
    """Return the default prompt or load a custom template from disk."""
    if path is None:
        return DEFAULT_PROMPT_TEMPLATE
    raw_value = str(path)
    if "\n" in raw_value or "{" in raw_value or "}" in raw_value:
        return raw_value
    candidate = Path(raw_value)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    return raw_value


def validate_prompt_template(template: str) -> None:
    """Ensure required placeholders exist before grading begins."""
    placeholders = {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name is not None
    }
    missing = REQUIRED_PROMPT_FIELDS - placeholders
    if missing:
        msg = (
            "Prompt template is missing required placeholders: "
            f"{', '.join(sorted(missing))}"
        )
        raise ValueError(msg)


def validate_scale_labels(
    *,
    scale_min: int,
    scale_max: int,
    scale_labels: dict[int, str],
) -> None:
    """Ensure scale labels fully cover the configured scoring range."""
    if scale_min > scale_max:
        raise ValueError("scale_min must be less than or equal to scale_max.")

    expected = set(range(scale_min, scale_max + 1))
    actual = set(scale_labels)

    if expected != actual:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        parts: list[str] = []
        if missing:
            parts.append(f"missing labels for: {missing}")
        if extra:
            parts.append(f"unexpected labels for: {extra}")
        raise ValueError("Invalid scale_labels; " + "; ".join(parts))

    blank = [score for score, label in scale_labels.items() if not label.strip()]
    if blank:
        raise ValueError(f"Scale labels must be non-empty for scores: {sorted(blank)}")


def render_scale_labels(scale_labels: dict[int, str]) -> str:
    """Render scale labels in a deterministic score-ascending format."""
    return "\n".join(
        f"{score}: {scale_labels[score].strip()}" for score in sorted(scale_labels)
    )


def render_result_fields(result_fields: Any) -> str:
    """Convert result fields to deterministic prompt text."""
    if isinstance(result_fields, str):
        return result_fields.strip()
    if isinstance(result_fields, dict):
        lines = [f"{key}: {value}" for key, value in result_fields.items()]
        return "\n".join(lines).strip()
    return json.dumps(result_fields, indent=2, sort_keys=True)


def render_domain_context(domain_context: str | None) -> str:
    """Render domain context as a labeled block or an empty string."""
    if domain_context is None or not domain_context.strip():
        return ""
    return f"Domain context:\n{domain_context.strip()}\n"


def render_output_instructions(response_mode: str) -> str:
    """Render mode-specific output instructions for the active response mode."""
    try:
        return DEFAULT_OUTPUT_INSTRUCTIONS[response_mode]
    except KeyError as exc:
        raise ValueError(f"Unsupported response_mode: {response_mode!r}") from exc


def build_prompt(
    *,
    query: str,
    result_fields: Any,
    scale_labels: dict[int, str] | None = None,
    domain_context: str | None = None,
    prompt_template: str | None = None,
    response_mode: str = "text",
) -> str:
    """Build a fully formatted grading prompt."""
    labels = scale_labels or DEFAULT_SCALE_LABELS
    template = prompt_template or DEFAULT_PROMPT_TEMPLATE
    validate_prompt_template(template)
    validate_scale_labels(
        scale_min=min(labels),
        scale_max=max(labels),
        scale_labels=labels,
    )
    return template.format(
        query=query.strip(),
        result_fields=render_result_fields(result_fields),
        scale_labels=render_scale_labels(labels),
        domain_context=render_domain_context(domain_context),
        output_instructions=render_output_instructions(response_mode),
    ).strip()
