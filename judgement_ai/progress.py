"""Terminal progress helpers for grading and validation runs."""

from __future__ import annotations

import sys

from judgement_ai.grader import GradeProgress


class TerminalProgressReporter:
    """Render grader progress events as compact terminal output."""

    def __init__(self, *, label: str) -> None:
        self.label = label

    def __call__(self, event: GradeProgress) -> None:
        if event.event == "start":
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
