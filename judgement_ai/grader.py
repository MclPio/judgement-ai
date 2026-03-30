"""Core grading orchestration."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any

import requests

from judgement_ai.fetcher import SearchResult
from judgement_ai.models import GradeResult
from judgement_ai.output import JsonResultsWriter, QuepidCsvWriter
from judgement_ai.prompts import (
    DEFAULT_SCALE_LABELS,
    build_prompt,
    load_prompt_template,
    validate_prompt_template,
    validate_scale_labels,
)
from judgement_ai.resume import load_completed_pairs

SCORE_PATTERN = re.compile(r"^SCORE:\s*(-?\d+)\s*$", re.MULTILINE)


@dataclass(slots=True)
class GradeFailure:
    """A failed query/document grading attempt after retries."""

    query: str
    doc_id: str
    rank: int
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


class Grader:
    """Coordinate fetching, grading, and result collection."""

    def __init__(
        self,
        *,
        fetcher: Any,
        llm_base_url: str,
        llm_api_key: str | None,
        llm_model: str,
        domain_context: str | None = None,
        scale_min: int = 0,
        scale_max: int = 3,
        scale_labels: dict[int, str] | None = None,
        max_workers: int = 10,
        passes: int = 1,
        prompt_template: str | None = None,
        max_retries: int = 3,
        request_timeout: float = 60.0,
    ) -> None:
        self.fetcher = fetcher
        self.llm_base_url = llm_base_url.rstrip("/")
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.domain_context = domain_context or ""
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.scale_labels = scale_labels or DEFAULT_SCALE_LABELS.copy()
        self.max_workers = max_workers
        self.passes = passes
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.prompt_template = load_prompt_template(prompt_template)
        validate_prompt_template(self.prompt_template)
        validate_scale_labels(
            scale_min=self.scale_min,
            scale_max=self.scale_max,
            scale_labels=self.scale_labels,
        )
        if self.passes < 1:
            raise ValueError("passes must be at least 1.")
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least 1.")

        self.last_failures: list[GradeFailure] = []
        self.last_summary = {"successes": 0, "failures": 0}

    def grade(
        self,
        *,
        queries: list[str],
        resume_from: str | None = None,
        failed_log_path: str | Path | None = "failed.json",
        output_path: str | Path | None = None,
        output_format: str | None = None,
        progress_callback: Callable[[GradeProgress], None] | None = None,
    ) -> list[GradeResult]:
        """Fetch and grade all results for the provided queries."""
        self.last_failures = []
        self.last_summary = {"successes": 0, "failures": 0, "skipped": 0}
        start_time = monotonic()

        completed_pairs = load_completed_pairs(resume_from) if resume_from else set()
        writer = self._build_output_writer(output_path=output_path, output_format=output_format)

        query_order = {query: index for index, query in enumerate(queries)}
        tasks: list[tuple[str, SearchResult]] = []
        skipped = 0
        for query in queries:
            for item in self.fetcher.fetch(query):
                if (query, item.doc_id) in completed_pairs:
                    skipped += 1
                    continue
                tasks.append((query, item))

        total = len(tasks)
        self._emit_progress(
            progress_callback,
            GradeProgress(
                event="start",
                total=total,
                completed=0,
                successes=0,
                failures=0,
                skipped=skipped,
                elapsed_seconds=monotonic() - start_time,
            ),
        )

        graded_results: list[GradeResult] = []
        failures: list[GradeFailure] = []
        completed = 0
        successes = 0
        failure_count = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._grade_result, query=query, item=item): (query, item)
                for query, item in tasks
            }
            for future in as_completed(future_map):
                result = future.result()
                completed += 1
                if isinstance(result, GradeFailure):
                    failures.append(result)
                    failure_count += 1
                    self._emit_progress(
                        progress_callback,
                        GradeProgress(
                            event="item_failed",
                            total=total,
                            completed=completed,
                            successes=successes,
                            failures=failure_count,
                            skipped=skipped,
                            elapsed_seconds=monotonic() - start_time,
                            query=result.query,
                            doc_id=result.doc_id,
                            attempts=result.attempts,
                        ),
                    )
                else:
                    graded_results.append(result)
                    successes += 1
                    if writer is not None:
                        writer.append(result)
                    self._emit_progress(
                        progress_callback,
                        GradeProgress(
                            event="item_completed",
                            total=total,
                            completed=completed,
                            successes=successes,
                            failures=failure_count,
                            skipped=skipped,
                            elapsed_seconds=monotonic() - start_time,
                            query=result.query,
                            doc_id=result.doc_id,
                        ),
                    )

        graded_results.sort(key=lambda item: (query_order[item.query], item.rank, item.doc_id))
        failures.sort(key=lambda item: (query_order[item.query], item.rank, item.doc_id))

        self.last_failures = failures
        self.last_summary = {
            "successes": len(graded_results),
            "failures": len(failures),
            "skipped": skipped,
        }

        if failed_log_path is not None and failures:
            self._write_failures(failures, failed_log_path)

        self._emit_progress(
            progress_callback,
            GradeProgress(
                event="finished",
                total=total,
                completed=completed,
                successes=len(graded_results),
                failures=len(failures),
                skipped=skipped,
                elapsed_seconds=monotonic() - start_time,
            ),
        )

        return graded_results

    def _build_output_writer(
        self,
        *,
        output_path: str | Path | None,
        output_format: str | None,
    ) -> JsonResultsWriter | QuepidCsvWriter | None:
        """Create an incremental output writer when configured."""
        if output_path is None:
            return None

        if output_format == "json":
            return JsonResultsWriter(output_path)
        if output_format == "quepid_csv":
            return QuepidCsvWriter(output_path)
        raise ValueError("output_format must be one of: 'json', 'quepid_csv', or None.")

    def _grade_result(self, *, query: str, item: SearchResult) -> GradeResult | GradeFailure:
        """Grade a single fetched result with retries."""
        last_error: Exception | None = None
        last_raw_response: str | None = None

        for _ in range(self.max_retries):
            try:
                pass_results = self._run_passes(query=query, item=item)
                final_score = self._select_final_score([score for score, _ in pass_results])
                final_reasoning = next(
                    reasoning
                    for score, reasoning in pass_results
                    if score == final_score
                )
                return GradeResult(
                    query=query,
                    doc_id=item.doc_id,
                    score=final_score,
                    reasoning=final_reasoning,
                    rank=item.rank,
                    pass_scores=[score for score, _ in pass_results],
                )
            except ParseError as exc:
                last_error = exc
                last_raw_response = exc.raw_response
            except Exception as exc:  # pragma: no cover - broad by design for retries
                last_error = exc

        return GradeFailure(
            query=query,
            doc_id=item.doc_id,
            rank=item.rank,
            error=str(last_error) if last_error else "Unknown grading failure.",
            attempts=self.max_retries,
            raw_response=last_raw_response,
        )

    def _run_passes(self, *, query: str, item: SearchResult) -> list[tuple[int, str]]:
        """Run one or more grading passes for a single result."""
        prompt = build_prompt(
            query=query,
            result_fields=item.fields,
            scale_labels=self.scale_labels,
            domain_context=self.domain_context,
            prompt_template=self.prompt_template,
        )
        return [self._grade_once(prompt=prompt) for _ in range(self.passes)]

    def _grade_once(self, *, prompt: str) -> tuple[int, str]:
        """Send one grading request and parse the response."""
        response_text = self._call_llm(prompt=prompt)
        return self.parse_response(response_text)

    def _call_llm(self, *, prompt: str) -> str:
        """Call an OpenAI-compatible chat completions endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"

        payload = {
            "model": self.llm_model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            msg = f"Failed to call LLM provider: {exc}"
            raise RuntimeError(msg) from exc

        data = response.json()
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response did not contain a chat completion message.") from exc

        if isinstance(message, str):
            return message

        if isinstance(message, list):
            text_parts = [
                part.get("text", "")
                for part in message
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            if text_parts:
                return "\n".join(text_parts)

        raise RuntimeError("LLM response message content was not a supported text format.")

    def parse_response(self, response_text: str) -> tuple[int, str]:
        """Parse reasoning and a strict SCORE line from the model response."""
        matches = SCORE_PATTERN.findall(response_text)
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
        if not self.scale_min <= score <= self.scale_max:
            raise ParseError(
                f"LLM response score {score} was outside the allowed range "
                f"{self.scale_min}-{self.scale_max}.",
                raw_response=response_text,
            )

        score_match = SCORE_PATTERN.search(response_text)
        assert score_match is not None
        reasoning = response_text[: score_match.start()].strip()
        return score, reasoning

    def _select_final_score(self, scores: list[int]) -> int:
        """Select the majority score, or the middle value when tied."""
        counts = Counter(scores)
        top_count = max(counts.values())
        winners = [score for score, count in counts.items() if count == top_count]
        if len(winners) == 1:
            return winners[0]

        sorted_scores = sorted(scores)
        return sorted_scores[len(sorted_scores) // 2]

    def _write_failures(
        self,
        failures: list[GradeFailure],
        path: str | Path,
    ) -> None:
        """Persist failed grading attempts for later inspection."""
        payload = [
            {
                "query": failure.query,
                "doc_id": failure.doc_id,
                "rank": failure.rank,
                "error": failure.error,
                "attempts": failure.attempts,
                **(
                    {"raw_response": failure.raw_response}
                    if failure.raw_response is not None
                    else {}
                ),
            }
            for failure in failures
        ]
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _emit_progress(
        self,
        callback: Callable[[GradeProgress], None] | None,
        event: GradeProgress,
    ) -> None:
        if callback is not None:
            callback(event)
