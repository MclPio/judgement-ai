# Pipeline

## Workflow

This repository follows a strict implementation pipeline:

1. Milestone definition
2. Task breakdown
3. Code implementation
4. Testing and verification

Each milestone must fully pass through all four stages before the next milestone starts.

## Milestone Template

### 1. Milestone

State the smallest end-to-end capability we want to ship next.

Example:

- Prompt system with default template and custom prompt validation

### 2. Task Breakdown

Break the milestone into concrete tasks with explicit outputs.

Example:

- Add default prompt template and scale labels
- Add prompt file loading
- Validate required placeholders
- Add focused unit tests
- Document prompt override behavior

### 3. Code

Implementation rules:

- Change only the files needed for the milestone
- Prefer small composable functions
- Keep CLI behavior thin and delegated into library code
- Add or update examples when public usage changes

### 4. Testing

Every milestone should define:

- Unit tests for expected behavior
- Failure-path tests for invalid input
- A manual verification note if external systems are involved

## Initial Milestones

### Milestone 0: Python project setup

Tasks:

- Create installable package with `pyproject.toml`
- Add package/test/examples/validate directories
- Add lint and test configuration
- Add CI workflow for test and lint

Verification:

- `pip install -e ".[dev]"`
- `pytest`
- `python -m judgement_ai.cli --help`

### Milestone 1: Prompt research and prompt module

Tasks:

- Capture research-backed prompt guidance
- Implement default prompt
- Implement custom prompt loading and validation
- Add unit tests for placeholder validation

Verification:

- Prompt validation tests pass
- README or docs cite the chosen sources

### Milestone 2: Fetchers

Tasks:

- Implement Elasticsearch fetcher
- Implement pre-fetched results file fetcher
- Normalize fetch output structure
- Add tests using fixtures or mocked HTTP responses

Verification:

- Fetchers return deterministic `SearchResult` objects
- Failure paths raise actionable errors

### Milestone 3: Grader core

Tasks:

- Build prompt payload from query and result fields
- Call LLM provider with OpenAI-compatible API
- Parse `SCORE: <integer>` strictly
- Add retry behavior and failed-run logging
- Add concurrency via `ThreadPoolExecutor`

Verification:

- Parsing tests pass
- Retry behavior is covered
- Failed items are persisted without aborting the whole run

### Milestone 4: Outputs and resume

Tasks:

- Implement incremental JSON output
- Implement Quepid CSV output
- Add resume set loading
- Skip previously completed `(query, doc_id)` pairs

Verification:

- Resume tests pass
- Incremental outputs are readable after partial runs

### Milestone 5: CLI

Tasks:

- Expose grade command
- Support config loading
- Wire fetcher selection, output selection, and resume mode
- Add CLI tests

Verification:

- Example commands run locally against fixtures

### Milestone 6: Validation and credibility

Tasks:

- Add validation support for smoke and Amazon product-search benchmarks
- Add local benchmark derivation tooling plus provenance notes
- Compute correlation against human labels
- Persist reproducible outputs and benchmark artifacts
- Document known limitations and tested models

Verification:

- Validation script runs from a clean checkout
- README claims match saved outputs when benchmark artifacts are published

Current follow-up work after milestone implementation:

- download and derive the local Amazon benchmark dataset
- run the benchmark with a real OpenAI-compatible or Ollama model
- review local artifacts and decide what, if anything, should be promoted into published docs
- then update README with observed metrics only after the outputs are approved

### Milestone 7: Local Validation Reliability

Purpose:

- make long-running local benchmark runs practical
- separate first-pass benchmarking from failure recovery
- make timeout/retry behavior configurable
- keep docs aligned with the implemented workflow
- keep the work shared across the library, main CLI, and validation runner

Tasks:

- Add configurable `request_timeout` to the shared grader and expose it through validation and the main CLI/config path
- Add configurable `max_retries` to the shared grader and expose it through validation and the main CLI/config path
- Change the recommended benchmark workflow to use a mostly single-pass first run, with retries handled later in a separate sweep
- Add a retry-sweep mode that reruns only failed rows from a prior validation artifact
- Add validation resume support so successful rows are not regraded unnecessarily
- Preserve and improve failure artifacts so timeout vs parse-format vs provider errors are easy to distinguish
- Keep the progress feedback shared across library/CLI/validation and ensure the new recovery flow also reports progress
- Update `README.md`, `AGENT.md`, and `docs/validation-runbook.md` when the behavior changes

Expected interfaces:

- Shared grader options:
  - `request_timeout`
  - `max_retries`
- Validation runner options:
  - `--request-timeout`
  - `--max-retries`
  - `--resume`
  - `--retry-failures PATH`
- Config support under `grading` for timeout and retries

Verification:

- A long local benchmark can run with `max_retries=1`
- Retry-only sweep reruns failed rows without repeating successful ones
- Resume mode skips already completed rows
- Timeout is configurable from validation and the main CLI/config path
- Docs accurately describe the local-model workflow
- Tests cover timeout, retry sweep, resume, and failure-artifact behavior

Documentation sync:

- `PIPELINE.md` is the source of truth for this upcoming work
- `README.md`, `AGENT.md`, and `docs/validation-runbook.md` must be updated once the behavior actually changes

Assumptions:

- This milestone is shared library + CLI + validation work, not validation-only work
- The focus is reliability and operator workflow, not benchmark methodology changes
- Documentation sync is part of the milestone, not an optional follow-up

## Branching And Review

- Prefer one milestone per branch or PR
- Keep each PR reviewable in under 500 lines when possible
- Do not mix validation data work with unrelated library changes

## Testing Standard

Before merging milestone work, run:

```bash
pytest
ruff check .
```

If external services are needed, provide a fixture or mock-first path so local tests remain fast and reliable.
