"""Parsing helpers for grading responses."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from judgement_ai.grading.types import ParseError

SCORE_PATTERN = re.compile(r"^SCORE:\s*(-?\d+)\s*$", re.MULTILINE)
SCORE_VARIANT_PATTERNS = [
    re.compile(r"^Score:\s*(-?\d+)\s*$", re.MULTILINE),
    re.compile(r"^\*\*Relevance Score:\*\*\s*(-?\d+)\s*$", re.MULTILINE),
]


def parse_text_response(
    response_text: str,
    *,
    scale_min: int,
    scale_max: int,
    allow_variants: bool = False,
) -> tuple[int, str]:
    """Parse reasoning and a score line from the model response."""
    matches = SCORE_PATTERN.findall(response_text)
    matched_pattern = SCORE_PATTERN
    if not matches and allow_variants:
        for pattern in SCORE_VARIANT_PATTERNS:
            matches = pattern.findall(response_text)
            if matches:
                matched_pattern = pattern
                break
    if not matches:
        raise ParseError(
            "LLM response did not contain a 'SCORE: <integer>' line.",
            raw_response=response_text,
        )
    if len(matches) > 1:
        raise ParseError(
            "LLM response contained multiple SCORE lines.",
            raw_response=response_text,
        )

    score = int(matches[0])
    if not scale_min <= score <= scale_max:
        raise ParseError(
            f"LLM response score {score} was outside the allowed range {scale_min}-{scale_max}.",
            raw_response=response_text,
        )

    score_match = matched_pattern.search(response_text)
    assert score_match is not None
    reasoning = response_text[: score_match.start()].strip()
    return score, reasoning


def decode_json_message(message: str) -> dict[str, Any]:
    """Decode a structured JSON response."""
    try:
        payload = json.loads(message)
    except json.JSONDecodeError as exc:
        raise ParseError(
            "LLM response was not valid JSON for structured output mode.",
            raw_response=message,
        ) from exc
    if not isinstance(payload, dict):
        raise ParseError(
            "LLM response JSON must decode to an object.",
            raw_response=message,
        )
    return payload


def parse_structured_response(
    response_payload: str | dict[str, Any],
    *,
    scale_min: int,
    scale_max: int,
) -> tuple[int, str]:
    """Parse score and reasoning from a structured JSON response."""
    payload = (
        decode_json_message(response_payload)
        if isinstance(response_payload, str)
        else response_payload
    )

    score = payload.get("score")
    if not isinstance(score, int):
        raise ParseError(
            "LLM response JSON did not contain an integer 'score'.",
            raw_response=json.dumps(payload),
        )
    if not scale_min <= score <= scale_max:
        raise ParseError(
            f"LLM response score {score} was outside the allowed range {scale_min}-{scale_max}.",
            raw_response=json.dumps(payload),
        )

    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str):
        raise ParseError(
            "LLM response JSON did not contain a string 'reasoning'.",
            raw_response=json.dumps(payload),
        )
    return score, reasoning.strip()


def build_json_schema(*, scale_min: int, scale_max: int) -> dict[str, Any]:
    """Return the structured response schema for grading."""
    return {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "minimum": scale_min,
                "maximum": scale_max,
            },
            "reasoning": {"type": "string"},
        },
        "required": ["score", "reasoning"],
        "additionalProperties": False,
    }


def select_final_score(scores: list[int]) -> int:
    """Select the majority score, or the middle value when tied."""
    counts = Counter(scores)
    top_count = max(counts.values())
    winners = [score for score, count in counts.items() if count == top_count]
    if len(winners) == 1:
        return winners[0]

    sorted_scores = sorted(scores)
    return sorted_scores[len(sorted_scores) // 2]
