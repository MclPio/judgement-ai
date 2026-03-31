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
- supports Elasticsearch and pre-fetched JSON input
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

### CLI with Elasticsearch

```bash
judgement-ai grade \
  --queries queries.txt \
  --elasticsearch https://my-elastic/catalog \
  --model gpt-5.1 \
  --api-key "$OPENAI_API_KEY" \
  --top-n 24 \
  --output judgments.csv
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

## Library Example

```python
from judgement_ai import FileResultsFetcher, Grader

fetcher = FileResultsFetcher(path="results.json")

grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
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

### Pre-fetched results file

`results.json` should look like:

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

An example config file is included at [judgement-ai.yaml.example](/Users/mclpio/repos/judgement-ai/judgement-ai.yaml.example).

For a fuller configuration reference, see [configuration.md](/Users/mclpio/repos/judgement-ai/docs/configuration.md).

## Providers

The tool supports:

- OpenAI-compatible endpoints via `base_url + api_key`
- Ollama locally

Behavior notes:

- `temperature` is fixed at `0`
- `json_schema` mode is supported when the provider and model support structured output
- some routed providers may require `text` mode even when the underlying model supports structured output elsewhere

## License

This project is licensed under [Elastic License 2.0](/Users/mclpio/repos/judgement-ai/LICENSE).

Plain-English intent:

- you can use `judgement-ai` in your own apps, workflows, and internal systems
- you can modify it for your own use
- you cannot offer `judgement-ai` itself as a hosted or managed service

This is source-available, not OSI open source.

## Optional Validation

The repo includes optional validation tooling against Amazon ESCI under [validate](/Users/mclpio/repos/judgement-ai/validate), but validation is not required to use the grading pipeline.

If you want to run the benchmark workflow, start with [validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md).

## Documentation

User-facing docs:

- [configuration.md](/Users/mclpio/repos/judgement-ai/docs/configuration.md)
- [validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md)
- [amazon-benchmark.md](/Users/mclpio/repos/judgement-ai/docs/amazon-benchmark.md)

Contributor-facing docs:

- [AGENT.md](/Users/mclpio/repos/judgement-ai/AGENT.md)
- [PIPELINE.md](/Users/mclpio/repos/judgement-ai/PIPELINE.md)

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Status

The core library and CLI are implemented and usable.

Validation tooling is present but benchmark claims are intentionally conservative until published results are finalized.
