# Validation Runbook

This guide is for running the hybrid benchmark workflow once you have:

- real derived benchmark subsets in place
- an OpenAI-compatible API endpoint
- a model you want to evaluate

The current repository already includes the validation framework. What remains is to replace the scaffold benchmark files with real derived subsets and then run the benchmarks against your chosen model.

## What Exists Already

The repo includes three validation modes:

- `smoke`
- `trec_dl_passage`
- `trec_product_search`

The validation entrypoint is:

```bash
.venv/bin/python validate/run_validation.py --help
```

Current benchmark file locations:

- `validate/datasets/smoke.json`
- `validate/datasets/trec_dl_passage.json`
- `validate/datasets/trec_product_search.json`

Canonical derivation scripts:

- `validate/prepare_trec_dl_passage.py`
- `validate/prepare_trec_product_search.py`

Current published artifact placeholders:

- `validate/published/trec_dl_passage/summary.json`
- `validate/published/trec_dl_passage/raw_judgments.json`
- `validate/published/trec_product_search/summary.json`
- `validate/published/trec_product_search/raw_judgments.json`

## What You Need To Do Next

### 1. Replace scaffold datasets with real derived subsets

Replace these two files with real benchmark subsets:

- `validate/datasets/trec_dl_passage.json`
- `validate/datasets/trec_product_search.json`

Required row shape:

```json
{
  "benchmark": "trec_dl_passage",
  "query_id": "123",
  "query": "example query",
  "doc_id": "doc-1",
  "rank": 1,
  "human_score": 3,
  "fields": {
    "passage_text": "Text to judge"
  }
}
```

For product search, `fields` can include richer metadata such as:

```json
{
  "title": "Product title",
  "brand": "Brand",
  "description": "Product description"
}
```

Recommendations:

- keep each canonical subset medium-sized
- stratify across relevance levels
- preserve real query text and the text shown to the judge
- keep provenance notes current in `validate/provenance/`
- fail derivation if any selected row cannot be fully resolved

### 1a. Build the TREC DL passage subset

Install validation extras first:

```bash
pip install -e ".[dev,validate]"
```

Then build the dataset with `ir-datasets`:

```bash
.venv/bin/python validate/prepare_trec_dl_passage.py \
  --per-label 50 \
  --output validate/datasets/trec_dl_passage.json
```

This script uses `msmarco-passage/trec-dl-2019/judged` by default and writes the final repo-ready JSON directly.

### 1b. Build the product-search subset

Point the script at the raw Amazon ESCI dataset directory or an examples parquet file, then run:

```bash
.venv/bin/python validate/prepare_trec_product_search.py \
  --input /path/to/esci-data \
  --per-label 50 \
  --output validate/datasets/trec_product_search.json
```

The script now handles the raw merge automatically when the directory contains files like:

- `shopping_queries_dataset_examples.parquet`
- `shopping_queries_dataset_products.parquet`

It also still accepts a pre-flattened `.csv` or `.jsonl` input if you already prepared one yourself.

Expected effective ESCI fields after loading/merge include:

- query or query_text
- product_id or doc_id or asin
- esci_label or label
- product_title or title
- optional brand and description fields

The script preserves source rank when present, otherwise it assigns deterministic source-order rank per query.

### 2. Configure your model endpoint

This validation runner works with any OpenAI-compatible endpoint. Two common setups are OpenRouter and Ollama.

### 2a. OpenRouter example

Since OpenRouter exposes an OpenAI-compatible interface, use:

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
  model: your-model-name
```

You can place that in a temporary YAML config file, for example `validation.local.yaml`.

Minimal example:

```yaml
llm:
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
  model: openai/gpt-4.1

grading:
  max_workers: 10
  passes: 1
```

If you use a different model later, only the `model` value needs to change.

### 2b. Ollama example

If you want to run a local 8B model through Ollama, use:

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: null
  model: your-ollama-model-name

grading:
  max_workers: 4
  passes: 1
```

Example:

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: null
  model: llama3.1:8b

grading:
  max_workers: 4
  passes: 1
```

Notes for local 8B runs:

- start with `smoke` before running canonical benchmarks
- keep worker count modest, usually `2-4`, because local inference can bottleneck quickly
- weaker models may fail the strict `SCORE:` format more often, so inspect `*-failures.json` if the benchmark run fails

### 3. Run smoke validation first

Always start with smoke mode:

```bash
OPENROUTER_API_KEY=... .venv/bin/python validate/run_validation.py \
  --benchmark smoke \
  --config validation.local.yaml \
  --output-dir validate/artifacts/smoke
```

This verifies:

- auth works
- the endpoint is reachable
- the model follows the `SCORE:` format
- artifact writing works
- your chosen local or hosted model is strong enough to be worth a full benchmark run

### 4. Run canonical benchmarks

General-search benchmark:

```bash
OPENROUTER_API_KEY=... .venv/bin/python validate/run_validation.py \
  --benchmark trec_dl_passage \
  --config validation.local.yaml \
  --output-dir validate/artifacts/trec_dl_passage
```

Product-search benchmark:

```bash
OPENROUTER_API_KEY=... .venv/bin/python validate/run_validation.py \
  --benchmark trec_product_search \
  --config validation.local.yaml \
  --output-dir validate/artifacts/trec_product_search
```

## Expected Outputs

Each run writes:

- `<benchmark>-raw-judgments.json`
- `<benchmark>-failures.json`
- `<benchmark>-aligned.json`
- `<benchmark>-summary.json`

Key files to inspect:

- raw judgments: the AI-produced scores/reasoning
- aligned rows: side-by-side human score and AI score
- summary: overall metric report and run status

## Publish Checklist

Only update README benchmark claims after all of these are true:

1. The scaffold benchmark datasets were replaced with real derived subsets.
2. Provenance notes were updated to describe the real source files and derivation process.
3. The canonical benchmark run completed with `status: completed`.
4. `num_failed_rows` is `0`.
5. Saved summary and raw judgments were copied into:
   - `validate/published/trec_dl_passage/`
   - `validate/published/trec_product_search/`
6. README numbers exactly match the saved summary artifacts.

## Suggested Workflow

Recommended order:

1. Replace benchmark subsets
2. Run `smoke`
3. Run `trec_dl_passage`
4. Run `trec_product_search`
5. Review aligned disagreements
6. Copy approved outputs into `validate/published/`
7. Update README with actual observed metrics

## Caveats

- The current checked-in canonical benchmark files are scaffolds, not publishable benchmark evidence.
- Canonical benchmarks are designed to fail if any rows are missing after retries.
- Product-search benchmark evidence supports ecommerce/product relevance claims, not supplement-specific claims.
- Supplement-specific validation is still a future custom benchmark step.
