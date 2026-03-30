# Validation Runbook

This repo now uses one real benchmark plus one tiny sanity-check mode:

- `smoke`
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

## Step 2: Build the Benchmark Dataset

Derive the local benchmark JSON:

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
- deterministic sampling
- around 200 rows total

Optional overrides:

- `--locale`
- `--full-task`
- `--per-label`
- `--dry-run`

## Step 3: Configure the Model

The validation runner works with any OpenAI-compatible endpoint.

### Ollama example

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: null
  model: llama3.1:8b

grading:
  max_workers: 2
  passes: 1
```

### Hosted endpoint example

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
  model: your-model-name

grading:
  max_workers: 4
  passes: 1
```

## Step 4: Run Smoke

Always run smoke first:

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark smoke \
  --config validation.local.yaml \
  --output-dir validate/artifacts/smoke
```

You should now see live progress in the terminal for every completed item, along with a short failure notice if any item exhausts retries.

## Step 5: Run the Amazon Benchmark

```bash
.venv/bin/python validate/run_validation.py \
  --benchmark amazon_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/amazon_product_search
```

Longer runs now show visible progress item by item so the command does not appear hung.

## Outputs

Each run writes:

- `<benchmark>-raw-judgments.json`
- `<benchmark>-failures.json`
- `<benchmark>-aligned.json`
- `<benchmark>-summary.json`

Inspect:

- summary for high-level metrics
- failures to see format-following or quality problems
- aligned rows to inspect human/AI disagreement

## Notes

- Raw and derived benchmark data under `validate/data/` is local-only and gitignored.
- `smoke` is for checking model behavior and formatting cheaply.
- `amazon_product_search` is the only real benchmark path in the repo now.
- Benchmark behavior is documented in [amazon-benchmark.md](/Users/mclpio/repos/judgement-ai/docs/amazon-benchmark.md).
