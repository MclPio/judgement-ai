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

from judgement_ai.fetcher import ResultsFetcher, SearchResult
from judgement_ai.models import GradeResult
from judgement_ai.output import JsonResultsWriter, ResultsWriter
from judgement_ai.prompts import (
    DEFAULT_SCALE_LABELS,
    build_prompt,
    load_prompt_template,
    validate_prompt_template,
    validate_scale_labels,
)
from judgement_ai.resume import load_completed_pairs

SCORE_PATTERN = re.compile(r"^SCORE:\s*(-?\d+)\s*$", re.MULTILINE)
SCORE_VARIANT_PATTERNS = [
    re.compile(r"^Score:\s*(-?\d+)\s*$", re.MULTILINE),
    re.compile(r"^\*\*Relevance Score:\*\*\s*(-?\d+)\s*$", re.MULTILINE),
]


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


class Grader:
    """Coordinate fetching, grading, and result collection."""

    def __init__(
        self,
        *,
        fetcher: ResultsFetcher,
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
        temperature: float = 0.0,
        provider: str = "auto",
        response_mode: str = "text",
        think: bool | None = None,
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
        self.temperature = temperature
        self.provider = provider
        self.response_mode = response_mode
        self.think = think
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
        if self.temperature < 0:
            raise ValueError("temperature must be greater than or equal to 0.")
        if self.provider not in {"auto", "ollama", "openai_compatible"}:
            raise ValueError("provider must be 'auto', 'ollama', or 'openai_compatible'.")
        if self.response_mode not in {"text", "json_schema"}:
            raise ValueError("response_mode must be 'text' or 'json_schema'.")

        self.last_failures: list[GradeFailure] = []
        self.last_summary = {"successes": 0, "failures": 0}

    @property
    def resolved_provider(self) -> str:
        """Resolve the concrete provider implementation."""
        if self.provider != "auto":
            return self.provider
        if "localhost:11434" in self.llm_base_url or "127.0.0.1:11434" in self.llm_base_url:
            return "ollama"
        return "openai_compatible"

    def grade(
        self,
        *,
        queries: list[str],
        resume_from: str | None = None,
        failed_log_path: str | Path | None = "failed.json",
        output_path: str | Path | None = None,
        output_format: str | None = None,
        progress_callback: Callable[[GradeProgress], None] | None = None,
        item_callback: GradeItemCallback | None = None,
    ) -> list[GradeResult]:
        """Fetch and grade all results for the provided queries."""
        self.last_failures = []
        self.last_summary = {"successes": 0, "failures": 0, "skipped": 0}
        start_time = monotonic()

        completed_pairs = load_completed_pairs(resume_from) if resume_from else set()
        writer = self._build_output_writer(output_path=output_path, output_format=output_format)
        query_order = {query: index for index, query in enumerate(queries)}
        tasks, skipped = self._collect_tasks(queries=queries, completed_pairs=completed_pairs)

        total = len(tasks)
        self._emit_progress_event(
            progress_callback=progress_callback,
            event="start",
            total=total,
            completed=0,
            successes=0,
            failures=0,
            skipped=skipped,
            start_time=start_time,
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
                successes, failure_count = self._handle_completed_result(
                    result=result,
                    graded_results=graded_results,
                    failures=failures,
                    writer=writer,
                    failed_log_path=failed_log_path,
                    progress_callback=progress_callback,
                    item_callback=item_callback,
                    total=total,
                    completed=completed,
                    successes=successes,
                    failure_count=failure_count,
                    skipped=skipped,
                    start_time=start_time,
                )

        graded_results.sort(key=lambda item: (query_order[item.query], item.rank, item.doc_id))
        failures.sort(key=lambda item: (query_order[item.query], item.rank, item.doc_id))

        self.last_failures = failures
        self.last_summary = {
            "successes": len(graded_results),
            "failures": len(failures),
            "skipped": skipped,
        }

        if failed_log_path is not None:
            failed_output_path = Path(failed_log_path)
            if failures:
                self._write_failures(failures, failed_output_path)
            elif failed_output_path.exists():
                failed_output_path.unlink()

        self._emit_progress_event(
            progress_callback=progress_callback,
            event="finished",
            total=total,
            completed=completed,
            successes=len(graded_results),
            failures=len(failures),
            skipped=skipped,
            start_time=start_time,
        )

        return graded_results

    def _collect_tasks(
        self,
        *,
        queries: list[str],
        completed_pairs: set[tuple[str, str]],
    ) -> tuple[list[tuple[str, SearchResult]], int]:
        """Collect all grading tasks while honoring resume state."""
        tasks: list[tuple[str, SearchResult]] = []
        skipped = 0
        for query in queries:
            for item in self.fetcher.fetch(query):
                if (query, item.doc_id) in completed_pairs:
                    skipped += 1
                    continue
                tasks.append((query, item))
        return tasks, skipped

    def _build_output_writer(
        self,
        *,
        output_path: str | Path | None,
        output_format: str | None,
    ) -> ResultsWriter | None:
        """Create the canonical incremental output writer when configured."""
        if output_path is None:
            return None

        if output_format not in {None, "json"}:
            raise ValueError("output_format must be 'json' or None.")
        return JsonResultsWriter(output_path)

    def _handle_completed_result(
        self,
        *,
        result: GradeResult | GradeFailure,
        graded_results: list[GradeResult],
        failures: list[GradeFailure],
        writer: ResultsWriter | None,
        failed_log_path: str | Path | None,
        progress_callback: Callable[[GradeProgress], None] | None,
        item_callback: GradeItemCallback | None,
        total: int,
        completed: int,
        successes: int,
        failure_count: int,
        skipped: int,
        start_time: float,
    ) -> tuple[int, int]:
        """Apply side effects for a completed grading future."""
        if isinstance(result, GradeFailure):
            failures.append(result)
            failure_count += 1
            if failed_log_path is not None:
                self._write_failures(failures, failed_log_path)
            self._emit_progress_event(
                progress_callback=progress_callback,
                event="item_failed",
                total=total,
                completed=completed,
                successes=successes,
                failures=failure_count,
                skipped=skipped,
                start_time=start_time,
                query=result.query,
                doc_id=result.doc_id,
                attempts=result.attempts,
            )
            if item_callback is not None:
                item_callback(result)
            return successes, failure_count

        graded_results.append(result)
        successes += 1
        if writer is not None:
            writer.append(result)
        self._emit_progress_event(
            progress_callback=progress_callback,
            event="item_completed",
            total=total,
            completed=completed,
            successes=successes,
            failures=failure_count,
            skipped=skipped,
            start_time=start_time,
            query=result.query,
            doc_id=result.doc_id,
        )
        if item_callback is not None:
            item_callback(result)
        return successes, failure_count

    def _grade_result(self, *, query: str, item: SearchResult) -> GradeResult | GradeFailure:
        """Grade a single fetched result with retries."""
        last_error: Exception | None = None
        last_raw_response: str | None = None
        failure_type = "unknown_error"

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
                failure_type = "parse_error"
            except ProviderError as exc:
                last_error = exc
                failure_type = exc.failure_type
            except Exception as exc:  # pragma: no cover - broad by design for retries
                last_error = exc
                failure_type = "unknown_error"

        return GradeFailure(
            query=query,
            doc_id=item.doc_id,
            rank=item.rank,
            failure_type=failure_type,
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
            response_mode=self.response_mode,
        )
        return [self._grade_once(prompt=prompt) for _ in range(self.passes)]

    def _grade_once(self, *, prompt: str) -> tuple[int, str]:
        """Send one grading request and parse the response."""
        response = self._call_llm(prompt=prompt)
        if self.response_mode == "json_schema":
            return self.parse_structured_response(response)
        if not isinstance(response, str):
            raise ParseError(
                "LLM text mode returned a non-text response.",
                raw_response=json.dumps(response),
            )
        return self.parse_response(response, allow_variants=True)

    def _call_llm(self, *, prompt: str) -> str | dict[str, Any]:
        """Call the configured LLM provider and return the message content."""
        if self.resolved_provider == "ollama":
            return self._call_ollama(prompt=prompt)
        return self._call_openai_compatible(prompt=prompt)

    def _call_openai_compatible(self, *, prompt: str) -> str | dict[str, Any]:
        """Call an OpenAI-compatible chat completions endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"

        payload: dict[str, Any] = {
            "model": self.llm_model,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.response_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "judgement_ai_grade_result",
                    "strict": True,
                    "schema": self._json_schema(),
                },
            }

        try:
            response = requests.post(
                f"{self.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            msg = f"LLM request timed out after {self.request_timeout} seconds."
            raise ProviderError(msg, failure_type="timeout") from exc
        except requests.RequestException as exc:
            msg = self._build_provider_error_message(exc)
            raise ProviderError(msg, failure_type="provider_error") from exc

        data = response.json()
        message = self._extract_openai_message_content(data)
        if self.response_mode == "json_schema":
            return self._decode_json_message(message)
        return message

    def _call_ollama(self, *, prompt: str) -> str | dict[str, Any]:
        """Call Ollama's native chat API for think control and structured outputs."""
        payload: dict[str, Any] = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if self.think is not None:
            payload["think"] = self.think
        if self.response_mode == "json_schema":
            payload["format"] = self._json_schema()

        try:
            response = requests.post(
                f"{self._ollama_api_root()}/api/chat",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            msg = f"LLM request timed out after {self.request_timeout} seconds."
            raise ProviderError(msg, failure_type="timeout") from exc
        except requests.RequestException as exc:
            msg = self._build_provider_error_message(exc)
            raise ProviderError(msg, failure_type="provider_error") from exc

        data = response.json()
        message = self._extract_ollama_message_content(data)
        if self.response_mode == "json_schema":
            return self._decode_json_message(message)
        return message

    def _extract_openai_message_content(self, data: dict[str, Any]) -> str:
        """Extract text content from an OpenAI-compatible chat completion."""
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "LLM response did not contain a chat completion message.",
                failure_type="provider_error",
            ) from exc

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

        raise ProviderError(
            "LLM response message content was not a supported text format.",
            failure_type="provider_error",
        )

    def _extract_ollama_message_content(self, data: dict[str, Any]) -> str:
        """Extract text content from an Ollama chat response."""
        try:
            message = data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(
                "LLM response did not contain an Ollama chat message.",
                failure_type="provider_error",
            ) from exc
        if not isinstance(message, str):
            raise ProviderError(
                "LLM response message content was not a supported text format.",
                failure_type="provider_error",
            )
        return message

    def _decode_json_message(self, message: str) -> dict[str, Any]:
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

    def _build_provider_error_message(self, exc: requests.RequestException) -> str:
        """Build a more actionable provider error message."""
        message = f"Failed to call LLM provider: {exc}"
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        response_text = self._response_text(response)
        if response_text:
            message = f"{message}. Response body: {response_text}"
        if status_code == 400 and self.response_mode == "json_schema":
            message = (
                f"{message}. If you are using a routed OpenAI-compatible provider, "
                "retry with text mode to confirm structured-output support."
            )
        return message

    def _response_text(self, response: Any) -> str | None:
        """Extract a short response body snippet from an HTTP error response."""
        if response is None:
            return None
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            return None
        compact = " ".join(text.split())
        if len(compact) <= 300:
            return compact
        return f"{compact[:297]}..."

    def parse_response(
        self,
        response_text: str,
        *,
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
        if not self.scale_min <= score <= self.scale_max:
            raise ParseError(
                f"LLM response score {score} was outside the allowed range "
                f"{self.scale_min}-{self.scale_max}.",
                raw_response=response_text,
            )

        score_match = matched_pattern.search(response_text)
        assert score_match is not None
        reasoning = response_text[: score_match.start()].strip()
        return score, reasoning

    def parse_structured_response(self, response_payload: str | dict[str, Any]) -> tuple[int, str]:
        """Parse score and reasoning from a structured JSON response."""
        payload = (
            self._decode_json_message(response_payload)
            if isinstance(response_payload, str)
            else response_payload
        )

        score = payload.get("score")
        if not isinstance(score, int):
            raise ParseError(
                "LLM response JSON did not contain an integer 'score'.",
                raw_response=json.dumps(payload),
            )
        if not self.scale_min <= score <= self.scale_max:
            raise ParseError(
                f"LLM response score {score} was outside the allowed range "
                f"{self.scale_min}-{self.scale_max}.",
                raw_response=json.dumps(payload),
            )

        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, str):
            raise ParseError(
                "LLM response JSON did not contain a string 'reasoning'.",
                raw_response=json.dumps(payload),
            )
        return score, reasoning.strip()

    def _json_schema(self) -> dict[str, Any]:
        """Return the structured response schema for grading."""
        return {
            "type": "object",
            "properties": {
                "score": {
                    "type": "integer",
                    "minimum": self.scale_min,
                    "maximum": self.scale_max,
                },
                "reasoning": {"type": "string"},
                "notes": {"type": "string"},
                "refusal": {"type": "string"},
            },
            "required": ["score", "reasoning"],
            "additionalProperties": False,
        }

    def _ollama_api_root(self) -> str:
        """Normalize an Ollama-compatible base URL to the native API root."""
        if self.llm_base_url.endswith("/v1"):
            return self.llm_base_url[: -len("/v1")]
        return self.llm_base_url.rstrip("/")

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
                "failure_type": failure.failure_type,
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

    def _emit_progress_event(
        self,
        *,
        progress_callback: Callable[[GradeProgress], None] | None,
        event: str,
        total: int,
        completed: int,
        successes: int,
        failures: int,
        skipped: int,
        start_time: float,
        query: str | None = None,
        doc_id: str | None = None,
        attempts: int | None = None,
    ) -> None:
        """Build and emit one structured progress event."""
        self._emit_progress(
            progress_callback,
            GradeProgress(
                event=event,
                total=total,
                completed=completed,
                successes=successes,
                failures=failures,
                skipped=skipped,
                elapsed_seconds=monotonic() - start_time,
                query=query,
                doc_id=doc_id,
                attempts=attempts,
            ),
        )
