# judgement-ai

`judgement-ai` is a Python library and CLI for generating judgment lists with an LLM.

It is built for workflows like:

- search relevance grading
- ranking experiments
- offline result review
- AI-assisted scoring pipelines

The core idea:

1. load queries
2. fetch or read candidate results
3. ask an LLM to score each `(query, document)` pair
4. write standard output that can feed the rest of your evaluation workflow

## What It Does

- grades search results with an OpenAI-compatible or Ollama-backed model
- supports file-backed and in-memory result inputs
- writes raw judgments JSON with optional CSV export
- runs concurrently for practical throughput
- writes incrementally so long runs are not lost
- supports resume and sidecar failure logs

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For local development (pytest and ruff):

```bash
pip install -e ".[dev]"
```

## Quickstart

### CLI with pre-fetched results

```bash
judgement-ai grade \
  --queries queries.txt \
  --results-file results.json \
  --model gpt-5.1 \
  --api-key "$OPENAI_API_KEY" \
  --output judgments.json
```

If you omit `--output`, the CLI creates a safe local raw-judgments path automatically.
When `judgments.json` already exists, it falls back to a timestamped path like
`judgments-20260407-153000.json` instead of overwriting silently.

### Local Ollama example

```bash
judgement-ai grade \
  --queries queries.txt \
  --results-file results.json \
  --base-url http://localhost:11434/v1 \
  --provider ollama \
  --model qwen3.5:9b \
  --response-mode json_schema \
  --no-think \
  --output judgments.json
```

### Preview prompt and request shape

```bash
judgement-ai preview \
  --config judgement-ai.yaml
```

`preview` is read-only. It uses built-in placeholder query and result data so you can inspect the
resolved prompt mode, provider, response mode, rendered prompt, and outgoing request payload shape
without configuring `queries` or `search.results_file`, and without spending provider time.

## Library Examples

### File-backed results

```python
from judgement_ai import FileResultsFetcher, Grader

fetcher = FileResultsFetcher(path="results.json")

grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
    temperature=0,
    response_mode="json_schema",
    max_attempts=1,
)

results = grader.grade(
    queries=["vitamin b6", "magnesium for sleep"],
    output_path="judgments.json",
)

print(len(results))
```

### In-memory results

```python
from judgement_ai import Grader, InMemoryResultsFetcher

fetcher = InMemoryResultsFetcher(
    {
        "vitamin b6": [
            {
                "doc_id": "123",
                "fields": {
                    "title": "Vitamin B6 100mg",
                    "description": "Supports energy metabolism",
                },
            }
        ]
    }
)

grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
)

results = grader.grade(queries=["vitamin b6"])
print(results[0].score)
```

## Fetchers

The grading layer only depends on a small fetcher contract:

```python
class ResultsFetcher(Protocol):
    def fetch(self, query: str) -> list[SearchResult]: ...
```

That means you can use the built-in fetchers:

- `FileResultsFetcher(path="results.json")`
- `InMemoryResultsFetcher({...})`

Or provide your own adapter for another backend, as long as it implements `fetch(query)`.

## Inputs

### Query file

Query files can be:

- plain text: one query per line
- CSV: first column or `query` column

Example:

```text
vitamin b6
tired all the time
magnesium for sleep
```

### Result inputs

The CLI reads a pre-fetched JSON file through `--results-file`.

Library users can either pass the same shape to `InMemoryResultsFetcher(...)` or store it in
`results.json` for `FileResultsFetcher(...)`.

The shape looks like:

```json
{
  "vitamin b6": [
    {
      "doc_id": "123",
      "rank": 1,
      "fields": {
        "title": "Vitamin B6 100mg",
        "description": "Supports energy metabolism"
      }
    }
  ]
}
```

This shape is intentionally simple and fixed for v1:

- top-level keys are query strings
- each value is a list of candidate results for that query
- `doc_id`, `rank`, and `fields` are the supported fields the loader cares about

Important behavior:

- the queries you pass to `grade(...)` must match those top-level keys if you want results back
- the grader uses `doc_id`, `rank`, and `fields`
- additional top-level attributes are ignored
- if `rank` is missing, the loader assigns one based on list position starting at `1`
- if you want extra document metadata to appear in the prompt, put it inside `fields`

For example, this will be visible to the model:

```json
{
  "vitamin b6": [
    {
      "doc_id": "123",
      "rank": 1,
      "fields": {
        "title": "Vitamin B6 100mg",
        "description": "Supports energy metabolism",
        "brand": "Example Labs"
      }
    }
  ]
}
```

## Outputs

The grading artifact is full-fidelity JSON.

### Raw Judgments JSON

```json
[
  {
    "query": "vitamin b6",
    "doc_id": "123",
    "score": 3,
    "reasoning": "Direct match for the product intent.",
    "rank": 1
  }
]
```

This raw JSON is the source of truth for:

- resume
- validation/retry flows
- detailed inspection of reasoning, rank, and optional `pass_scores`

### Optional CSV Export

```csv
query,docid,rating
vitamin b6,123,3
magnesium for sleep,456,2
```

This export is intentionally lossy and omits reasoning, rank, and pass scores.

You can produce it during grading with `--csv-output judgments.csv`, or later from any
canonical raw judgments artifact:

```bash
judgement-ai export-csv \
  --input judgments.json \
  --output judgments.csv
```

## Resume And Failure Handling

Long runs are meant to be recoverable.

- successful results are written incrementally
- failed items are written to a sidecar `*-failures.json`
- `--resume` skips already completed `(query, doc_id)` pairs from the raw JSON artifact
- `--max-attempts 1` means one attempt now, then rely on the failure log or a later rerun if needed

Example:

```bash
judgement-ai grade \
  --queries queries.txt \
  --results-file results.json \
  --model gpt-5.1 \
  --api-key "$OPENAI_API_KEY" \
  --output judgments.json \
  --resume
```

If the output file already exists and you are not resuming, the CLI will ask before overwriting it.
Use `--force` to overwrite without a prompt.

To also export CSV from the canonical raw JSON:

```bash
judgement-ai grade \
  --queries queries.txt \
  --results-file results.json \
  --model gpt-5.1 \
  --api-key "$OPENAI_API_KEY" \
  --output judgments.json \
  --csv-output judgments.csv
```

Config-driven runs can also be fully one-command if the config includes queries, search input,
and optional output paths:

```bash
judgement-ai grade --config judgement-ai.yaml
```

## Configuration

An example config file is included at [judgement-ai.yaml.example](docs/judgement-ai.yaml.example).

For a fuller configuration reference, see [configuration.md](docs/configuration.md).

The config supports three clear customization levels:

- curated defaults only
- structured prompt tuning through `grading.prompt.instructions` and `grading.prompt.output_instructions`
- full custom prompt ownership through `grading.prompt_file`

If you choose `prompt_file`, it is intentionally not hybrid mode. Only `{query}` and `{result_fields}` are injected at runtime. Scale labels, domain context, and structured prompt overrides are not mixed in.

## Providers

The tool supports:

- OpenAI-compatible endpoints via `base_url + api_key`
- Ollama locally

Behavior notes:

- `temperature` defaults to `0`, but is configurable through the library, CLI, and config file
- `text` is the default and recommended mode for the broadest reliability
- `json_schema` is supported as an optional mode when the provider and model reliably support structured output
- structured output is mainly about output-format reliability, not inherently better grading quality
- some routed providers may require `text` mode even when the underlying model supports structured output elsewhere
- advanced provider-specific request tuning lives in config under `llm.openai_compatible` and `llm.ollama`

For CLI runs, use `--temperature`. For config-driven runs, set `grading.temperature`.

Prompt and grading tunings such as prompt mode, `response_mode`, temperature, attempts, timeouts, and provider passthrough are documented in [configuration.md](docs/configuration.md).

## License

This project is licensed under the [MIT License](LICENSE).

## Documentation

User-facing docs:

- [README.md](README.md)
- [configuration.md](docs/configuration.md)

Agent facing docs:

- [AGENT.md](docs/AGENT.md)
- [PIPELINE.md](docs/PIPELINE.md)

## Development

```bash
pip install -e ".[dev]"
python3 -m pytest
python3 -m ruff check .
```
