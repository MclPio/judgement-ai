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
  max_retries: 1
  request_timeout: 60
  response_mode: text
  prompt_file: null

output:
  format: json
  path: judgments.json

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

Provide a pre-fetched JSON results file:

```yaml
search:
  results_file: results.json
```

For file-backed grading, the query strings you pass must match the top-level keys in `results.json`.

Supported result item fields for v1 are:

- `doc_id`
- `rank`
- `fields`

Anything you want the model to see should live under `fields`.
Other top-level attributes are ignored by the fetcher.

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

### `max_retries`

Attempts per item before it is recorded as a failure.

For exploratory or long local runs, `1` is usually the best choice.

### `request_timeout`

Provider request timeout in seconds.

Local models often need larger values like `180-300`.

### `response_mode`

One of:

- `text`
- `json_schema`

Use `json_schema` when the provider route reliably supports structured output.
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

### `format`

One of:

- `json`
- `quepid_csv`

If omitted in the CLI, the tool can infer the format from the output file extension.

### `path`

Where to write the judgments file.

The CLI also writes a sidecar failure log next to it:

- `judgments.json`
- `judgments-failures.json`

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
  max_retries: 1
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
  max_retries: 1
  request_timeout: 300
  response_mode: json_schema
```
