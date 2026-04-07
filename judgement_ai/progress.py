"""Terminal progress helpers for grading and validation runs."""

from __future__ import annotations

import sys

from judgement_ai.grading import GradeProgress


class TerminalProgressReporter:
    """Render grader progress events as compact terminal output."""

    def __init__(
        self,
        *,
        label: str,
        output_path: str | None = None,
        resume: bool = False,
    ) -> None:
        self.label = label
        self.output_path = output_path
        self.resume = resume
        self._announced_context = False

    def __call__(self, event: GradeProgress) -> None:
        if event.event == "start":
            self._announce_context()
            self._render_line(event)
            return

        if event.event == "item_failed":
            self._render_line(event)
            sys.stderr.write("\n")
            sys.stderr.write(
                f"[{self.label}] failed query={event.query!r} doc_id={event.doc_id!r} "
                f"after {event.attempts} attempts\n"
            )
            sys.stderr.flush()
            return

        if event.event == "item_completed":
            self._render_line(event)
            return

        if event.event == "finished":
            self._render_line(event)
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _render_line(self, event: GradeProgress) -> None:
        sys.stderr.write(
            "\r"
            f"[{self.label}] {event.completed}/{event.total} completed"
            f" | ok={event.successes}"
            f" | failed={event.failures}"
            f" | skipped={event.skipped}"
            f" | {event.elapsed_seconds:.1f}s"
        )
        sys.stderr.flush()

    def _announce_context(self) -> None:
        if self._announced_context:
            return

        if self.output_path:
            action = "Resuming raw judgments at" if self.resume else "Writing raw judgments to"
            sys.stderr.write(f"[{self.label}] {action} {self.output_path}\n")
            sys.stderr.flush()

        self._announced_context = True
