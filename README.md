# judgement-ai

`judgement-ai` is a Python library and CLI for generating judgment lists with an LLM.

It is built for workflows like:

- search relevance grading
- ranking experiments
- offline result review
- AI-assisted scoring pipelines

The core idea is simple:

1. load queries
2. fetch or read candidate results
3. ask an LLM to score each `(query, document)` pair
4. write standard output that can feed the rest of your evaluation workflow

## What It Does

- grades search results with an OpenAI-compatible or Ollama-backed model
- supports file-backed and in-memory result inputs
- writes Quepid-compatible CSV or detailed JSON
- runs concurrently for practical throughput
- writes incrementally so long runs are not lost
- supports resume and sidecar failure logs

## What It Does Not Do

- compute IR metrics like NDCG or MRR
- optimize search queries
- provide a web UI
- train or fine-tune models

`judgement-ai` is the grading step, not the whole evaluation stack.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For local development:

```bash
pip install -e ".[dev]"
```

For optional validation tooling:

```bash
pip install -e ".[dev,validate]"
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
    max_retries=1,
)

results = grader.grade(
    queries=["vitamin b6", "magnesium for sleep"],
    output_path="judgments.json",
    output_format="json",
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

The canonical shape looks like:

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

### Quepid CSV

```csv
query,docid,rating
vitamin b6,123,3
magnesium for sleep,456,2
```

### JSON

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

## Resume And Failure Handling

Long runs are meant to be recoverable.

- successful results are written incrementally
- failed items are written to a sidecar `*-failures.json`
- `--resume` skips already completed `(query, doc_id)` pairs

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

## Configuration

An example config file is included at [judgement-ai.yaml.example](judgement-ai.yaml.example).

For a fuller configuration reference, see [configuration.md](docs/configuration.md).

## Providers

The tool supports:

- OpenAI-compatible endpoints via `base_url + api_key`
- Ollama locally

Behavior notes:

- `temperature` defaults to `0`, but is configurable through the library, CLI, and config file
- `json_schema` mode is supported when the provider and model support structured output
- some routed providers may require `text` mode even when the underlying model supports structured output elsewhere

For CLI runs, use `--temperature`. For config-driven runs, set `grading.temperature`.

Prompt and grading tunings such as `prompt_file`, `response_mode`, temperature, retries, and timeouts are documented in [configuration.md](docs/configuration.md).

## License

This project is licensed under the [MIT License](LICENSE).

## Optional Validation

The repo includes optional validation tooling against Amazon ESCI under [`validate/`](validate), but validation is not required to use the grading pipeline.

If you want to run the benchmark workflow, start with [validation-runbook.md](docs/validation-runbook.md).

## Documentation

User-facing docs:

- [configuration.md](docs/configuration.md)
- [validation-runbook.md](docs/validation-runbook.md)
- [amazon-benchmark.md](docs/amazon-benchmark.md)

Contributor-facing docs:

- [AGENT.md](AGENT.md)
- [PIPELINE.md](PIPELINE.md)

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Status

The core library and CLI are implemented and usable.

Validation tooling is present but benchmark claims are intentionally conservative until published results are finalized.

# REFACTOR BRANCH TODO
- Add ability to select profiles, instead of passing parameters when calling in the grader, users should be able to have config files that contain all necessary settings, prompt context, end points etc... This was possbile before the refactor but it was done in prompts.py in a bad way. Validation currently has no way to load a profile.

- 
