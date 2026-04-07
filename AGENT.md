# AGENT.md

## Purpose

This repo builds `judgement-ai`: a small Python library and CLI for grading `(query, document)` pairs with an LLM and writing canonical raw judgments JSON, with optional CSV export.

Start here, then read `PIPELINE.md` for the current milestone queue.

## Repo Map

- `judgement_ai/cli.py`: thin CLI with `grade` and `export-quepid`
- `judgement_ai/grader.py`: grading orchestration, provider calls, retries, parsing
- `judgement_ai/fetcher.py`: pre-fetched JSON and in-memory fetchers
- `judgement_ai/prompts.py`: default prompt, prompt loading, placeholder validation
- `judgement_ai/output.py`: canonical JSON writer and CSV export
- `judgement_ai/resume.py`: resume from existing raw judgments JSON
- `judgement_ai/validation.py`: benchmark execution, alignment, metrics, analysis, gates
- `judgement_ai/validation_prep.py`: dataset preparation helpers used by `validate/`
- `validate/`: optional validation scripts, smoke dataset, provenance notes
- `tests/`: source of truth for supported behavior

## Current Product Shape

What is clearly implemented now:

- Library-first design with a thin Click CLI
- Pre-fetched JSON results as the main grading input
- Canonical raw judgments JSON as the source of truth
- Optional Quepid CSV export, either during grading or later
- Resume support based on existing raw judgments JSON
- Sidecar failure logs for long-running or partial runs
- Provider support for OpenAI-compatible APIs and Ollama
- `text` and `json_schema` response modes
- Optional validation flows, including a checked-in smoke dataset and Amazon-oriented helpers

What is not the core product story:

- fetching from live search backends
- ranking metrics like NDCG or MRR
- a UI
- benchmark claims not backed by committed artifacts

## Working Rules

- Treat code and tests as more trustworthy than old markdown.
- Keep `AGENT.md` short; put milestone detail in `PIPELINE.md`.
- Before running repo commands, activate the local environment with `source .venv/bin/activate`.
- Use `python3`, not `python`, for repo commands and examples.
- Prefer small, direct changes in the library before adding CLI complexity.
- Preserve the current canonical artifact contract:
  - raw judgments output is JSON
  - resume reads that JSON
  - CSV export is derived from that JSON
- When behavior changes, update tests and docs in the same pass.
- Avoid expanding validation scope unless it supports the core library story.

## Plan-Code-Test Loop

Follow the harness-style loop for each milestone:

1. Plan: read the relevant module(s), tests, and `PIPELINE.md`; define the smallest end-to-end change.
2. Code: implement only what the milestone needs, keeping CLI wrappers thin.
3. Test: run the narrowest useful tests first, then broader repo checks before closing the milestone.

Do not treat planning as separate from execution. A milestone is only done when the code and tests match the updated docs.

## Test Commands

Use the smallest command that proves the change, then widen as needed:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_prompts.py`
- `python3 -m pytest tests/test_grader.py`
- `python3 -m pytest tests/test_cli.py`
- `python3 -m pytest tests/test_validation.py tests/test_run_validation_entrypoint.py`
- `python3 -m pytest`
- `python3 -m ruff check .`

## Documentation Standard

- `AGENT.md` is the entrypoint, not the encyclopedia.
- `PIPELINE.md` is the active implementation board.
- README should describe current user-facing behavior only.
- Validation numbers or quality claims must match saved artifacts exactly.
