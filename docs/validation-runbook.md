# Validation Runbook

This repo now uses one real benchmark plus one tiny sanity-check mode:

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

## Step 3: Configure the Model

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

### Hosted endpoint example

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
  model: your-model-name
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

## Step 4: Run Smoke

Always run smoke first:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark smoke \
  --config validation.local.yaml \
  --output-dir validate/artifacts/smoke
```

You should now see live progress in the terminal for every completed item, along with a short failure notice if any item exhausts retries.

## Step 5: Run Local Calibration

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search_calibration \
  --config validation.local.yaml \
  --output-dir validate/artifacts/calibration_local
```

Local calibration must pass these gates before the full benchmark:

- timeout failures: `0`
- total failures: `<= 5%`
- scored output uses at least `3` labels
- no single AI score bucket exceeds `70%` of scored rows

## Step 6: Run Reference Calibration

Run the same calibration benchmark with a stronger hosted judge:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search_calibration \
  --config validation.reference.yaml \
  --output-dir validate/artifacts/calibration_reference
```

Reference calibration must pass these gates before the full benchmark:

- timeout failures: `0`
- parse failures: `0`
- no score collapse
- Spearman `>= 0.50`

If the reference calibration fails, stop and revisit the benchmark slice or prompt design before rerunning the full benchmark.

## Step 7: Run The Full Amazon Benchmark

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/amazon_product_search
```

Recommended local-model workflow:

- Start with `grading.max_retries: 1` so the first pass keeps moving.
- Use `response_mode: json_schema` and `provider: ollama` for local Qwen/Ollama runs.
- Disable thinking explicitly for local Ollama runs with `llm.think: false`.
- Use a larger `grading.request_timeout` for slower local models.
- Let the first pass finish, then rerun only failed rows in a clean second sweep.

Longer runs now show visible progress item by item so the command does not appear hung.

## Step 8: Resume Or Retry Only Failures

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

Calibration runs also write:

- `amazon_product_search_calibration-local-gate.json`
- `amazon_product_search_calibration-reference-gate.json`

## Notes

- Raw and derived benchmark data under `validate/data/` is local-only and gitignored.
- `smoke` is for checking endpoint behavior and artifact plumbing cheaply.
- `amazon_product_search_calibration` is the fast gate before a full run.
- `amazon_product_search` is the main benchmark.
- Retry sweeps require an existing `<benchmark>-raw-judgments.json` file in the output directory.
- Validation defaults to Amazon ESCI prompt semantics and JSON-schema output on supported providers.
- Benchmark behavior is documented in [amazon-benchmark.md](/Users/mclpio/repos/judgement-ai/docs/amazon-benchmark.md).
