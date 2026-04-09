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

### M4. Prompt And Configuration Usability

Plan:

- make prompt customization easy to discover and safe to use
- document exactly what can be customized and what template variables are required
- confirm whether the current config surface already covers the important prompt controls cleanly

Code focus (using old file locations, be careful):

- `judgement_ai/prompts.py`
- `judgement_ai/config.py`
- `judgement_ai/cli.py`
- `docs/configuration.md`
- `README.md`

Test minimum:

- `source .venv/bin/activate`
- `ruff check`
- `python3 -m pytest`

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

### M9. Preview Command

Plan:

- add a dedicated `judgement-ai preview` command so users can inspect the resolved prompt and request shape before grading
- keep v1 intentionally simple and always available by using built-in placeholder data instead of loading real query/result files
- help users verify prompt mode, provider resolution, response mode, and advanced config effects without spending provider time or debugging a live run

Behavior agreed for v1:

- command name is `judgement-ai preview`
- use placeholder input by default, not the first real query/result
- placeholder query should be a simple example string
- placeholder result should include `title` and `description`, not URL
- preview should work even if `queries` and `search.results_file` are not configured
- print:
  - prompt mode
  - resolved provider
  - response mode
  - rendered prompt
  - request payload shape
- redact any sensitive values if they appear in preview output
- do not make any provider network calls

Code focus:

- `judgement_ai/cli/main.py`
- `judgement_ai/cli/common.py`
- `judgement_ai/cli/commands/preview.py`
- `judgement_ai/prompts.py`
- `judgement_ai/grading/providers.py`
- `README.md`
- `docs/configuration.md`

Implementation notes:

- reuse the same config-loading and override resolution path as `grade` where practical
- build the prompt exactly the same way the grader would, but with placeholder query/result fields
- expose the resolved payload as a preview artifact without sending it
- keep this read-only and side-effect free
- do not add a real-data preview mode in v1

Test minimum:

- `source .venv/bin/activate`
- `python3 -m pytest tests/test_cli.py tests/test_prompts.py tests/test_grader.py`
- `python3 -m ruff check .`

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
