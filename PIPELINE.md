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

### Milestone 8: Amazon Benchmark Quality And Calibration

Purpose:

- keep Amazon ESCI as the benchmark source
- improve the derived slice so it stays deterministic but becomes less query-skewed
- add a smaller fixed calibration slice so broken prompt/model setups are caught before another long run

Tasks:

- Replace the current per-label sampler with a deterministic round-robin sampler by query within each label
- Keep benchmark defaults:
  - source: Amazon ESCI
  - locale: `us`
  - reduced Task 1 only
  - target size: `200`
  - per-label target: `50`
- Use this sampling rule:
  - group rows by `human_score`
  - within each label, group rows by `query`
  - sort queries by `query_id`, then rows within query by `rank`, then `doc_id`
  - select one row per query per pass until the per-label cap is reached
- Add a second derived artifact:
  - `amazon_product_search_calibration.json`
  - fixed size: `48` rows
  - `12` rows per label
  - generated with the same deterministic round-robin logic
- Add a benchmark derivation report printed by the prep script and saved as JSON with:
  - total candidates
  - per-label counts
  - unique query count
  - top query frequencies
  - title/brand/description coverage and blank-ish counts
- Do not hand-curate or manually remove hard queries; improve the derivation policy instead

Verification:

- Rerunning derivation with the same source files yields byte-identical benchmark JSON
- The 200-row slice remains label-balanced
- Query concentration is materially reduced versus the current slice
- The calibration slice is stable and reproducible

### Milestone 9: Amazon-Specific Structured Judge

Purpose:

- stop using a generic IR relevance prompt for an ecommerce ESCI benchmark
- eliminate most parse failures with structured output
- make the local Qwen/Ollama path explicit instead of relying on prompt hacks

Tasks:

- Add an `amazon_esci` prompt profile for validation
- Make Amazon validation default to ESCI-aware labels:
  - `0`: Irrelevant, does not satisfy the shopping intent
  - `1`: Complement, related add-on/accessory but not the product sought
  - `2`: Substitute, different product that plausibly satisfies the same shopping need
  - `3`: Exact or near-exact match to the intended product
- Ensure Amazon validation prompt rules explicitly handle:
  - hard constraints like `without`, compatibility, quantity, capacity, and material
  - brand constraints
  - price ceilings like `$5 items`
  - size and age qualifiers like `toddler` vs `youth`
  - short or ambiguous queries conservatively
  - no broad intent inflation from a single character or partial token
- Add structured output mode as the default validation path:
  - schema contains at minimum `score` and `reasoning`
  - optional `refusal` or `notes` field is allowed
- Add provider-aware output control:
  - `llm.provider`: `auto | ollama | openai_compatible`
  - `grading.response_mode`: `json_schema | text`
  - `llm.think: false` support for Ollama-backed runs
- Use `json_schema` by default when supported, with text parsing only as fallback
- Keep a text fallback parser, but harden it to accept mild score variants only in fallback mode:
  - `Score: 1`
  - `**Relevance Score:** 1`
  - still reject ambiguous or multi-score outputs
- Keep `temperature = 0`; do not add temperature tuning work in this milestone

Expected interfaces:

- Shared grader options:
  - `provider`
  - `response_mode`
  - `think`
- Validation config:
  - `llm.provider`
  - `llm.think`
  - `grading.response_mode`
  - `grading.prompt_profile`
- Validation runner options:
  - `--provider`
  - `--response-mode`
  - `--think` and `--no-think`, or an equivalent explicit false-setting flag

Verification:

- Structured-output validation runs produce parseable output without regex dependence on supported providers
- The Ollama path can disable thinking explicitly
- Amazon validation uses ESCI semantics by default
- `smoke` passes with structured output enabled

### Milestone 10: Live Validation Artifacts And Rerun Gates

Purpose:

- make long runs observable while they are happening
- make failures immediately inspectable
- prevent another full benchmark run until prompt/model behavior is sane on a smaller gate

Tasks:

- Write validation artifacts incrementally during the run:
  - append failures immediately
  - rewrite summary after each completed item
  - rewrite aligned rows after each completed item for validation runs
- Add a lightweight benchmark-analysis artifact after each run with:
  - failure counts by type
  - parse failures with empty vs non-empty raw output
  - AI score distribution
  - per-query failure concentration
  - score-collapse warnings
- Update the runbook workflow to:
  1. run `smoke`
  2. run the `48`-row calibration slice locally
  3. run the same calibration slice with a stronger hosted reference judge
  4. only then run the full `200`-row local benchmark
- Add a documented two-track validation setup:
  - `validation.local.yaml` for local Ollama/Qwen
  - `validation.reference.yaml.example` for a stronger OpenAI-compatible sanity run
- Update the recommended `validation.local.yaml` to:

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: null
  model: qwen3.5:9b
  provider: ollama
  think: false

grading:
  max_workers: 1
  passes: 1
  max_retries: 1
  request_timeout: 300
  response_mode: json_schema
  prompt_profile: amazon_esci
```

- Add these calibration gates before the next full run:
  - local calibration:
    - timeout failures: `0`
    - total failures: `<= 5%`
    - score distribution uses at least `3` of `4` labels
    - no single AI score bucket exceeds `70%` of scored rows
  - reference calibration:
    - timeout failures: `0`
    - parse failures: `0`
    - no score collapse
    - Spearman `>= 0.50`
- If the reference calibration fails, stop and revisit benchmark and prompt design before another full run
- If the reference passes but local fails, treat it as a local-model limitation rather than a benchmark validity problem

Verification:

- The failures file appears live during runs
- Summary and aligned files reflect current state before run completion
- The local config avoids wasted inline retries
- Calibration gate logic blocks full reruns when the setup is still obviously broken

Documentation sync:

- `docs/amazon-benchmark.md` must describe the improved deterministic sampling policy and the calibration slice
- `docs/validation-runbook.md` must document the two-track local/reference workflow and rerun gates
- `README.md` and `AGENT.md` must reflect structured output, ESCI-specific judging, and live artifact behavior once implemented

Assumptions:

- Amazon ESCI remains the benchmark source
- The current Amazon slice is reproducible but not yet a strong headline benchmark slice
- Sampling will be improved rather than manually curating rows
- Validation will use a two-track workflow:
  - local model as the operator workflow
  - stronger hosted reference model as the sanity-check path
- Structured output is the primary path, not prompt-only text parsing
- `temperature = 0` stays fixed and is not treated as the main cause of the failed run

### Milestone 11: Fast Thesis Test And Validation Runbook Reset

Purpose:

- get a decisive answer quickly on whether the idea still has promise
- stop wasting time on local-model runs before a trustworthy reference upper bound exists
- replace hard-to-understand blocking gates with a simpler reference-first runbook
- keep `temperature = 0` fixed and treat it as a non-issue for now

Tasks:

- Record that this milestone temporarily supersedes the current “full local benchmark first” flow
- Use this sequencing:
  1. derive the current Amazon benchmark and calibration slice
  2. run `smoke` locally
  3. run one strong frontier reference calibration
  4. if that passes a viability threshold, run the full reference `200`-row benchmark
  5. only then run local calibration and local full runs as comparison or cost-saving follow-up
- Explicitly document that:
  - the current Amazon slice is acceptable for one fast thesis test
  - sampler redesign is deferred until after the reference verdict
  - the local gate must not hard-block exploratory full runs
  - the reference track is the deciding signal
- Rewrite the validation runbook around diagnosis instead of blocking:
  - build datasets
  - run local smoke
  - run frontier reference calibration
  - run full reference benchmark if calibration is viable
  - then run local calibration and local full benchmark as comparison
  - keep `max_retries: 1`, high local timeout, and `--resume` / `--retry-failures` cleanup
- Change gate behavior:
  - reference calibration gate stays meaningful
  - local calibration gate becomes advisory
  - the full benchmark command hard-blocks only when there is no passing reference calibration
  - blocker messaging must name exact failed conditions
- Freeze the current benchmark slice for this decisive test:
  - do not change sampling again before the next reference verdict
  - if the strong reference run fails badly, revisit slice construction and prompt semantics next
  - if the strong reference run succeeds reasonably, treat the current slice as sufficient for continued iteration
- Keep `temperature = 0` fixed in configs and docs; do not add temperature tuning work in this milestone

Reference calibration interpretation:

- if parse failures > `0`, the structured-output or provider path is not stable enough
- if a score-collapse warning appears, the judge setup is not usable yet
- if Spearman `< 0.40`, stop and revisit prompt or benchmark fit before any full run
- if Spearman is `0.40 - 0.59`, continue to the full reference benchmark but treat the thesis as uncertain
- if Spearman `>= 0.60`, continue confidently to the full reference benchmark

Full reference benchmark interpretation:

- if full-reference Spearman `< 0.50`, the thesis is in serious doubt and should pause for benchmark or prompt redesign
- if full-reference Spearman is `0.50 - 0.69`, continue iterating but do not publish credibility claims
- if full-reference Spearman `>= 0.70`, continue with local-model comparison and optimization

Verification:

- gate logic allows the full benchmark when the reference gate passes even if the local gate fails
- gate logic blocks the full benchmark when the reference gate fails and names the exact failed checks
- the runbook and config examples match the new reference-first flow
- `temperature = 0` remains fixed
- local config remains single-pass and structured-output-first

Documentation sync:

- `docs/validation-runbook.md` becomes the operator-facing source of truth for the reference-first thesis test
- `README.md` and `AGENT.md` must reflect that local-model results are secondary evidence until the reference upper bound is known

Assumptions:

- Amazon ESCI stays as the benchmark source
- the current slice is acceptable for a fast thesis test, but not yet for publication-quality claims
- one stronger paid reference run is allowed and required
- local-model results are secondary evidence until the reference upper bound is known
- `temperature = 0` remains fixed

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
