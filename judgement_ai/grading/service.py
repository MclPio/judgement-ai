"""Core grading orchestration service."""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import monotonic
from typing import Any

from judgement_ai.fetcher import ResultsFetcher, SearchResult
from judgement_ai.grading.parsing import (
    build_json_schema,
    parse_structured_response,
    parse_text_response,
    select_final_score,
)
from judgement_ai.grading.providers import call_llm, ollama_api_root, resolve_provider
from judgement_ai.grading.types import (
    GradeFailure,
    GradeItemCallback,
    GradeProgress,
    ParseError,
    ProviderError,
)
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
        max_attempts: int = 1,
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
        self.max_attempts = max_attempts
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
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
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
        return resolve_provider(llm_base_url=self.llm_base_url, provider=self.provider)

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
        for _ in range(self.max_attempts):
            try:
                pass_results = self._run_passes(query=query, item=item)
                final_score = self._select_final_score([score for score, _ in pass_results])
                final_reasoning = next(
                    reasoning for score, reasoning in pass_results if score == final_score
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
            attempts=self.max_attempts,
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
        return call_llm(
            llm_base_url=self.llm_base_url,
            llm_api_key=self.llm_api_key,
            llm_model=self.llm_model,
            temperature=self.temperature,
            provider=self.provider,
            response_mode=self.response_mode,
            think=self.think,
            request_timeout=self.request_timeout,
            prompt=prompt,
            scale_min=self.scale_min,
            scale_max=self.scale_max,
        )

    def parse_response(
        self,
        response_text: str,
        *,
        allow_variants: bool = False,
    ) -> tuple[int, str]:
        """Parse reasoning and a score line from the model response."""
        return parse_text_response(
            response_text,
            scale_min=self.scale_min,
            scale_max=self.scale_max,
            allow_variants=allow_variants,
        )

    def parse_structured_response(self, response_payload: str | dict[str, Any]) -> tuple[int, str]:
        """Parse score and reasoning from a structured JSON response."""
        return parse_structured_response(
            response_payload,
            scale_min=self.scale_min,
            scale_max=self.scale_max,
        )

    def _json_schema(self) -> dict[str, Any]:
        """Return the structured response schema for grading."""
        return build_json_schema(scale_min=self.scale_min, scale_max=self.scale_max)

    def _ollama_api_root(self) -> str:
        """Normalize an Ollama-compatible base URL to the native API root."""
        return ollama_api_root(self.llm_base_url)

    def _select_final_score(self, scores: list[int]) -> int:
        """Select the majority score, or the middle value when tied."""
        return select_final_score(scores)

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
