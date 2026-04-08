# Configuration Guide

This guide covers the main runtime configuration for `judgement-ai`.

If you just want to get started, copy [judgement-ai.yaml.example](../judgement-ai.yaml.example) and adjust the values.

## File Layout

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-5.1

search:
  results_file: results.json

grading:
  scale_min: 0
  scale_max: 3
  scale_labels:
    0: "Completely irrelevant"
    1: "Related but not relevant"
    2: "Relevant"
    3: "Perfectly relevant"
  domain_context: "Nutritional supplements catalog"
  max_workers: 10
  passes: 1
  temperature: 0
  max_attempts: 1
  request_timeout: 60
  response_mode: text
  prompt_file: null

output:
  path: judgments.json
  csv_path: judgments.csv

queries: queries.txt
```

Environment variables like `${OPENAI_API_KEY}` are expanded automatically.

## `llm`

### `base_url`

OpenAI-compatible base URL.

Examples:

- `https://api.openai.com/v1`
- `https://openrouter.ai/api/v1`
- `http://localhost:11434/v1`

### `api_key`

API key string or environment-variable reference.

For Ollama, `null` is fine.

### `model`

Model identifier understood by the configured provider.

Examples:

- `gpt-5.1`
- `openai/gpt-5.4`
- `qwen3.5:9b`

### `provider`

Optional. One of:

- `auto`
- `ollama`
- `openai_compatible`

If omitted, the tool infers the provider from the base URL where possible.

### `think`

Optional Ollama-only control.

- `false` is a good default for local grading when thinking-heavy models are too slow

## `search`

The CLI reads a pre-fetched JSON results file:

```yaml
search:
  results_file: results.json
```

Library users can also pass the same query-to-results shape directly to
`InMemoryResultsFetcher(...)`.

Example results payload:

```json
{
  "vitamin b6": [
    {
      "doc_id": "123",
      "fields": {
        "title": "Vitamin B6 100mg",
        "description": "Supports energy metabolism"
      }
    }
  ]
}
```

The query strings you pass must match the top-level keys in the results payload if you want
results back.

Supported result item fields for v1 are:

- `doc_id`
- `rank`
- `fields`

Anything you want the model to see should live under `fields`.
Other top-level attributes are ignored by the fetcher.
If `rank` is omitted, the fetcher assigns one based on the result's position in the list,
starting at `1`.

## `grading`

### Scale

Default scale is `0-3`.

If you customize the scale, provide labels for every score in the configured range.

### `domain_context`

Optional context injected into the prompt.

Useful when the search domain is specialized.

### `max_workers`

Maximum concurrent grading workers.

- hosted providers: often `4-10`
- local Ollama models: usually `1-2`

### `passes`

Number of grading passes per item.

Default is `1`.

### `temperature`

Sampling temperature for the model.

- `0` is the safest default for reproducible grading
- higher values allow more variation, but can reduce consistency across runs

For judgment-list generation, `0` or a very low value is usually the right starting point.

Set this in config with `grading.temperature`, or override it per run with `--temperature`.

### `max_attempts`

Total attempts per item before it is recorded as a failure.

Examples:

- `1`: try each item once, then write failures for later cleanup
- `2`: one retry after the first failure
- `3`: up to three total attempts

For exploratory or long local runs, `1` is usually the best first-pass choice.

### `request_timeout`

Provider request timeout in seconds.

Local models often need larger values like `180-300`.

### `response_mode`

One of:

- `text`
- `json_schema`

`text` is the default and recommended mode for the broadest compatibility.

Use `json_schema` when the provider route reliably supports structured output and you want stricter machine-readable responses.

Structured output is mainly a reliability feature for parsing and validation. Do not assume it improves grading quality by itself.

If you see provider `400` errors on routed services, test `text` mode.

### `prompt_file`

Optional path to a custom prompt template.

Required placeholders:

- `{query}`
- `{result_fields}`
- `{scale_labels}`

Optional placeholders:

- `{domain_context}`
- `{output_instructions}`

This is the main prompt override hook for the core tool.

## `output`

### `path`

Where to write the canonical raw judgments JSON file.

This should be a `.json` path.

The CLI also writes a sidecar failure log next to it:

- `judgments.json`
- `judgments-failures.json`

Resume and retry logic use this canonical raw JSON artifact.

If `output.path` is omitted entirely, the CLI falls back to a safe local default:

- `judgments.json` when that path does not exist
- `judgments-YYYYMMDD-HHMMSS.json` when `judgments.json` already exists

### `csv_path`

Optional CSV export path derived from the canonical raw judgments JSON.

This export is lossy by design and includes only:

- `query`
- `docid`
- `rating`

## `queries`

Path to the query file.

Supported formats:

- text, one query per line
- CSV, first column or `query` column

## CLI Overrides

CLI flags override config-file values.

Typical pattern:

```bash
judgement-ai grade \
  --config judgement-ai.yaml \
  --model gpt-5.1 \
  --output judgments.json
```

If your config already provides the canonical output path and optional `csv_path`, a full run can
be as simple as:

```bash
judgement-ai grade --config judgement-ai.yaml
```

## Recommended Starting Points

### Hosted OpenAI-compatible provider

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-5.1

grading:
  max_workers: 4
  passes: 1
  temperature: 0
  max_attempts: 1
  request_timeout: 60
  response_mode: json_schema
```

### Local Ollama

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
  temperature: 0
  max_attempts: 1
  request_timeout: 300
  response_mode: json_schema
```
