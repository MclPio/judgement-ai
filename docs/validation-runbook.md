# Validation Runbook

This runbook is now optimized for a **fast thesis test**.

The goal is to answer three questions quickly:

1. Can a strong reference judge produce a viable result on this Amazon benchmark?
2. If yes, how far behind is the local model?
3. If no, is the problem more likely prompt/benchmark fit than local-model quality?

This repo uses one real benchmark plus one tiny sanity-check mode:

- `smoke`
- `amazon_product_search_calibration`
- `amazon_product_search`

## Setup

Create a virtual environment and install validation dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,validate]"
```

## Step 1: Download Amazon ESCI Data

Download the raw Amazon files into the local validation cache:

```bash
.venv/bin/python validate/download_amazon_esci.py
```

Default download location:

- `validate/data/amazon_esci/`

This downloads the official source files needed for derivation.

## Step 2: Build The Benchmark Datasets

Derive the local benchmark JSON, the smaller calibration slice, and the derivation report:

```bash
.venv/bin/python validate/prepare_amazon_product_search.py \
  --download \
  --input validate/data/amazon_esci \
  --per-label 50 \
  --output validate/data/amazon_product_search.json
```

Default behavior:

- locale: `us`
- task view: reduced Task 1 only
- deterministic round-robin sampling by query within each label
- `amazon_product_search.json`: about 200 rows total
- `amazon_product_search_calibration.json`: 48 rows total
- `amazon_product_search_report.json`: derivation report and field coverage stats

Optional overrides:

- `--locale`
- `--full-task`
- `--per-label`
- `--calibration-per-label`
- `--dry-run`

## Step 3: Configure The Models

The validation runner works with any OpenAI-compatible endpoint.

### Ollama example

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

### Reference endpoint example

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
  model: your-strong-reference-model
  provider: openai_compatible

grading:
  max_workers: 4
  passes: 1
  max_retries: 1
  request_timeout: 180
  response_mode: json_schema
  prompt_profile: amazon_esci
```

The repo also includes [validation.reference.yaml.example](/Users/mclpio/repos/judgement-ai/validation.reference.yaml.example) as a starting point for the reference-model track.

Important:

- The decisive reference verdict must use a **strong non-lite model**.
- Do **not** use `lite`, `flash-lite`, or `mini-preview` class models as the only reference verdict.
- Keep `temperature = 0` fixed. This runbook does not treat temperature as an active tuning variable.

## Step 4: Run Smoke

Always run smoke first:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark smoke \
  --config validation.local.yaml \
  --output-dir validate/artifacts/smoke
```

You should now see live progress in the terminal for every completed item, along with a short failure notice if any item exhausts retries.

## Step 5: Run Frontier Reference Calibration

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search_calibration \
  --config validation.reference.yaml \
  --output-dir validate/artifacts/calibration_reference
```

This is the primary go/no-go step.

Interpret the result like this:

- if parse failures > `0`: the structured-output or provider path is not stable enough
- if a score-collapse warning appears: the judge setup is not usable yet
- if Spearman `< 0.40`: stop and revisit prompt or benchmark fit before any full run
- if Spearman is `0.40 - 0.59`: continue to the full **reference** benchmark, but treat the thesis as uncertain
- if Spearman `>= 0.60`: continue confidently to the full reference benchmark

## Step 6: Run The Full Reference Benchmark

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.reference.yaml \
  --output-dir validate/artifacts/reference_full
```

This establishes the best current upper bound for the thesis.

If the full run is blocked, treat that as a signal that the reference calibration did not pass.
The blocker should now tell you the exact failed condition, for example:

- `Reference calibration failed: spearman 0.304068 < 0.40`
- `Reference calibration failed: score collapse warning`
- `Reference calibration failed: 2 parse failures`

Interpret the full reference result like this:

- if full-reference Spearman `< 0.50`: the thesis is in serious doubt and should pause for benchmark or prompt redesign
- if full-reference Spearman is `0.50 - 0.69`: continue iterating, but do not publish credibility claims
- if full-reference Spearman `>= 0.70`: continue with local-model comparison and optimization

## Step 7: Run Local Calibration

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search_calibration \
  --config validation.local.yaml \
  --output-dir validate/artifacts/calibration_local
```

Local calibration is now **advisory**, not blocking.

Use it to estimate how far behind the local model is and to catch obvious local-provider problems.

Good local calibration signals:

- timeout failures: `0`
- total failures: `<= 5%`
- scored output uses at least `3` labels
- no single AI score bucket exceeds `70%` of scored rows

Poor local calibration no longer blocks the full local benchmark as long as the reference path has already shown viability.

## Step 8: Run The Full Local Benchmark

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/amazon_product_search
```

Recommended local-model workflow:

- keep `grading.max_retries: 1`
- keep `response_mode: json_schema`
- keep `provider: ollama`
- keep `llm.think: false`
- keep a high `grading.request_timeout`
- let the first pass finish, then clean up with resume or retry sweeps
- the full local run now depends on the **reference** calibration verdict, not the local calibration verdict

## Step 9: Resume Or Retry Only Failures

Resume a partially completed run without regrading successful rows:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/amazon_product_search \
  --resume
```

Retry only the rows that failed in the previous run:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/amazon_product_search \
  --retry-failures validate/artifacts/amazon_product_search/amazon_product_search-failures.json
```

Useful overrides:

- `--request-timeout 240`
- `--max-retries 1`

## Outputs

Each run writes:

- `<benchmark>-raw-judgments.json`
- `<benchmark>-failures.json`
- `<benchmark>-aligned.json`
- `<benchmark>-summary.json`
- `<benchmark>-analysis.json`

Inspect:

- summary for high-level metrics
- failures to see timeout, provider, or format-following problems
- aligned rows to inspect human/AI disagreement
- analysis for score distribution, empty-raw parse failures, and query concentration

Calibration runs write gate files:

- `amazon_product_search_calibration-local-gate.json`
- `amazon_product_search_calibration-reference-gate.json`

Only the **reference** gate is a hard blocker for the full benchmark in the current thesis-test flow.
The local gate is diagnostic only.

## Notes

- Raw and derived benchmark data under `validate/data/` is local-only and gitignored.
- The current deterministic 200-row Amazon slice is frozen for one fast thesis test.
- Do not resample before the next strong reference verdict unless you find a clear derivation bug.
- `smoke` is for checking endpoint behavior and artifact plumbing cheaply.
- `amazon_product_search_calibration` is the fast diagnosis slice.
- `amazon_product_search` is the main benchmark.
- Retry sweeps require an existing `<benchmark>-raw-judgments.json` file in the output directory.
- Validation defaults to Amazon ESCI prompt semantics and JSON-schema output on supported providers.
- The full benchmark is hard-blocked only when there is no **passing reference** calibration gate, unless you use `--skip-calibration-gates`.
- Benchmark behavior is documented in [amazon-benchmark.md](/Users/mclpio/repos/judgement-ai/docs/amazon-benchmark.md).
