from __future__ import annotations

from judgement_ai.grader import GradeProgress
from judgement_ai.progress import TerminalProgressReporter


def test_terminal_progress_reporter_writes_compact_progress_lines(capsys) -> None:
    reporter = TerminalProgressReporter(label="validation:smoke")

    reporter(
        GradeProgress(
            event="start",
            total=3,
            completed=0,
            successes=0,
            failures=0,
            skipped=0,
            elapsed_seconds=0.1,
        )
    )
    reporter(
        GradeProgress(
            event="item_completed",
            total=3,
            completed=1,
            successes=1,
            failures=0,
            skipped=0,
            elapsed_seconds=0.2,
            query="vitamin b6",
            doc_id="123",
        )
    )
    reporter(
        GradeProgress(
            event="finished",
            total=3,
            completed=3,
            successes=3,
            failures=0,
            skipped=0,
            elapsed_seconds=1.2,
        )
    )

    captured = capsys.readouterr()
    assert "[validation:smoke] 3/3 completed" in captured.err
    assert "ok=3" in captured.err


def test_terminal_progress_reporter_writes_failure_notice(capsys) -> None:
    reporter = TerminalProgressReporter(label="grade")
    reporter(
        GradeProgress(
            event="item_failed",
            total=2,
            completed=1,
            successes=0,
            failures=1,
            skipped=0,
            elapsed_seconds=0.5,
            query="vitamin b6",
            doc_id="bad-doc",
            attempts=3,
        )
    )

    captured = capsys.readouterr()
    assert "failed query='vitamin b6' doc_id='bad-doc' after 3 attempts" in captured.err
