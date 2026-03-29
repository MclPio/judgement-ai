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

- Add benchmark subset and reproduction script
- Compute correlation against human labels
- Publish reproducible outputs
- Document known limitations and tested models

Verification:

- Validation script runs from a clean checkout
- README claims match saved outputs

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

