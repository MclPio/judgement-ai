# Pipeline

## How To Use This File

Read `AGENT.md` first. Then use this file to choose the next milestone and run it through:

1. Plan
2. Code
3. Test

Keep milestones small enough that one pass can finish end-to-end.

## Current Baseline

The current codebase already supports:

- grading from query files plus pre-fetched JSON results
- canonical raw judgments JSON output
- optional CSV export through `--csv-output` or `export-csv`
- config loading from YAML
- retries, request timeouts, concurrency, and resume
- `text` and `json_schema` response modes
- optional validation helpers and scripts under `validate/`

The most reliable source for this baseline is `tests/`, not old milestone notes.

Local command convention:

- activate `.venv` first with `source .venv/bin/activate`
- use `python3`, not `python`

## Milestone Template

For each milestone, write down:

- plan: the smallest user-visible or architecture-visible outcome
- code: the files that should change
- test: the exact commands that prove it works

If a milestone changes public behavior, update docs in the same pass.

## Active Milestones

### M2. Structured Output Reliability Decision

Plan:

- verify whether `json_schema` mode is reliable enough for OpenAI-compatible APIs to keep as a first-class path
- compare current repo behavior with manual provider checks outside the codebase before changing implementation
- decide among:
  - keep both `text` and `json_schema`
  - keep `json_schema` only as optional best-effort behavior
  - remove `json_schema` from the core product path
- decide separately whether Ollama structured output is worth keeping or is unnecessary complexity

Code focus:

- `judgement_ai/grader.py`
- `tests/test_grader.py`
- `docs/structured-output-checks.md`
- user-facing docs that describe response modes

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_grader.py tests/test_cli.py`
- `python3 -m ruff check .`

### M3. Retry And Failure-Recovery Semantics

Plan:

- verify whether `max_retries=0` should be supported
- keep recovery behavior easy to understand for users who prefer single-pass runs plus later failure retries
- clarify the relationship between retries, failure logs, resume, and any retry-failures workflow

Code focus:

- `judgement_ai/grader.py`
- `judgement_ai/cli.py`
- `judgement_ai/validation.py`
- tests and docs covering failure recovery

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_grader.py tests/test_cli.py tests/test_resume.py tests/test_validation.py`

### M4. Prompt And Configuration Usability

Plan:

- make prompt customization easy to discover and safe to use
- document exactly what can be customized and what template variables are required
- confirm whether the current config surface already covers the important prompt controls cleanly

Code focus:

- `judgement_ai/prompts.py`
- `judgement_ai/config.py`
- `judgement_ai/cli.py`
- `docs/configuration.md`
- `README.md`

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_prompts.py tests/test_config.py tests/test_cli.py`


### M6. Validation Scope Simplification

Plan:

- decide whether validation should stay in this repo at all
- if it stays, keep it simple: prepared inputs in, `judgement_ai` package run, artifacts out
- remove data acquisition and benchmark-lab complexity if that is no longer the package’s responsibility

Code focus:

- `judgement_ai/validation.py`
- `validate/`
- docs mentioning validation

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_validation.py tests/test_validation_prep.py tests/test_prepare_benchmarks.py tests/test_run_validation_entrypoint.py`

### M7. Markdown Rewrite Pass

Plan:

- rewrite markdown files to be short, current, and pleasant to read
- keep `AGENT.md` as the entrypoint, `PIPELINE.md` as the work board, and trim or merge the rest as needed
- remove stale milestone history and confusing internal notes

Code focus:

- `AGENT.md`
- `PIPELINE.md`
- `README.md`
- `docs/*.md`


### M8. License Review

Plan:

- compare keeping MIT versus moving to Apache-2.0 or another license
- document the tradeoff and change only once the project direction is clear

Code focus:

- `LICENSE`
- `README.md`
- packaging metadata if needed

Test minimum:

- no code tests required unless packaging metadata changes

## Default Execution Order

Unless the user redirects, work in this order one at a time:

1. M1. Architecture And Code Organization Review
2. M2. Structured Output Reliability Decision
3. M3. Retry And Failure-Recovery Semantics
4. M4. Prompt And Configuration Usability
5. M5. Naming And Output Language Cleanup
6. M6. Validation Scope Simplification
7. M7. Markdown Rewrite Pass
8. M8. License Review

## Exit Criteria

A milestone is complete when:

- the plan was implemented, not just described
- focused tests pass
- broader checks were run when the change crosses module boundaries
- docs match the shipped behavior
- the next milestone can start without re-reading stale notes
