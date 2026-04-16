# AGENT.md

## Purpose

This repo builds `judgement-ai`: a small Python library and CLI for grading `(query, document)` pairs with an LLM and writing raw judgments JSON, with optional CSV export.

Start here, then read `PIPELINE.md` for the current milestone queue.

## Repo Map

- `judgement_ai/cli/`: CLI package with `grade` and `export-csv`
- `judgement_ai/grading/`: grading package with orchestration, provider calls, retries, and parsing
- `judgement_ai/fetcher.py`: pre-fetched JSON and in-memory fetchers
- `judgement_ai/prompts.py`: default prompt, prompt loading, placeholder validation
- `judgement_ai/output.py`: JSON writer and CSV export
- `judgement_ai/resume.py`: resume from existing raw judgments JSON
- `tests/`: source of truth for supported behavior

## Current Product Shape

What is clearly implemented now:

- Library design with a Click CLI
- Pre-fetched JSON results as the main grading input
- raw judgments JSON as the source of truth
- Optional CSV export, either during grading or later
- Resume support based on existing raw judgments JSON
- Sidecar failure logs for long-running or partial runs
- Provider support for OpenAI-compatible APIs and Ollama
- `text` and `json_schema` response modes
- Optional validation flows, including a checked-in smoke dataset and Amazon-oriented helpers

## Working Rules

- Keep `AGENT.md` short; put milestone detail in `PIPELINE.md`.
- Before running repo commands, activate the local environment with `source .venv/bin/activate`.
- When behavior changes, update tests and docs in the same pass.

## Plan-Code-Test Loop

Follow the harness-style loop for each milestone:

1. Plan: read the relevant module(s), tests, and `PIPELINE.md`.
2. Code: implement what the milestone needs.
3. Test: write and run tests, then broader repo checks before closing the milestone.

Do not treat planning as separate from execution. A milestone is only done when the code and tests match the updated docs.

## Test Commands

- `source .venv/bin/activate`
- `python -m pytest`
- `python -m ruff check .`

## Documentation Standard

- `AGENT.md` is the entrypoint, not the encyclopedia.
- `PIPELINE.md` is the active implementation board.
- README should introduce the repo, and describe current user-facing behavior.