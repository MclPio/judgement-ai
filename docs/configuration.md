# Configuration Guide

This guide covers the main runtime configuration for `judgement-ai`.

Copy [judgement-ai.yaml.example](../judgement-ai.yaml.example) and trim it down to the parts you need.

## File Layout

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-5.1
  # provider: openai_compatible
  # think: false
  # openai_compatible:
  #   top_p: 0.9
  #   provider:
  #     require_parameters: true
  # ollama:
  #   keep_alive: "15m"
  #   options:
  #     top_k: 20

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
  prompt:
    # instructions: |
    #   You are grading supplement search results.
    # output_instructions: |
    #   First explain your reasoning briefly, then output SCORE: <number>
  prompt_file: null

output:
  path: judgments.json
  csv_path: judgments.csv

queries: queries.txt
```

Environment variables like `${OPENAI_API_KEY}` are expanded automatically.

## Prompt Modes

`judgement-ai` supports two prompt modes.

### 1. Structured Prompt Config

This is the default and recommended mode.

You keep the repo's prompt shape, scale rendering, and parser behavior, but override the main instruction blocks:

```yaml
grading:
  scale_labels:
    0: "Completely irrelevant"
    1: "Related but not relevant"
    2: "Relevant"
    3: "Perfectly relevant"
  domain_context: "Nutritional supplements catalog"
  prompt:
    instructions: |
      You are grading supplement search results for an internal relevance audit.
    output_instructions: |
      First explain your reasoning briefly, then output SCORE: <number>
```

Supported structured prompt keys:

- `grading.prompt.instructions`
- `grading.prompt.output_instructions`

In this mode, these still participate:

- `grading.scale_min`
- `grading.scale_max`
- `grading.scale_labels`
- `grading.domain_context`
- `grading.response_mode`

### 2. Full Custom Prompt File

This is the full-ownership mode.

```yaml
grading:
  prompt_file: examples/custom_prompt_template.txt
```

In this mode:

- only `{query}` and `{result_fields}` are required supported placeholders
- `grading.scale_min`, `grading.scale_max`, `grading.scale_labels`, and `grading.domain_context` must not be set, everything must be inside the prompt file
- `grading.prompt.*` must not be set
- `--domain` must not be used alongside `--prompt-file`

The repo includes [examples/custom_prompt_template.txt](../examples/custom_prompt_template.txt) as a starting point.

Once you choose `prompt_file`, you own the prompt semantics. The library still handles runtime injection of the query and result fields, but it does not mix in scale labels, domain context, or output instructions. Be careful of how you describe the output it produces, as judgement-ai grader needs the output to be `SCORE: <integer>` for text parsing and json of a specific shape `{"score": <integer>, "reasoning": <string>}`

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
- `openai/gpt-5.4-mini`
- `qwen3.5:9b`

### `provider`

Optional. One of:

- `auto`
- `ollama`
- `openai_compatible`

If omitted, the tool infers the provider from the base URL where possible.

Set this explicitly when you want provider-specific advanced config blocks to apply.

### `think`

Optional Ollama-only control.

- `false` is a good default for local grading when thinking heavy models are too slow

### `openai_compatible`

Optional advanced passthrough block for provider-specific chat payload fields.

Example:

```yaml
llm:
  provider: openai_compatible
  openai_compatible:
    top_p: 0.9
    max_completion_tokens: 200
    seed: 1
    provider:
      require_parameters: true
```

Notes:

- this block is config-only, not a CLI flag surface
- it applies only when `llm.provider: openai_compatible`
- it is merged into the outgoing chat payload after the curated fields are built
- it must not override curated settings such as `model`, `temperature`, or `response_format`

### `ollama`

Optional advanced passthrough block for Ollama-native chat fields.

Example:

```yaml
llm:
  provider: ollama
  ollama:
    keep_alive: "15m"
    options:
      top_k: 20
      top_p: 0.9
      seed: 1
```

Notes:

- this block is config-only, not a CLI flag surface
- it applies only when `llm.provider: ollama`
- root-level Ollama fields like `keep_alive` are supported
- nested `ollama.options` is merged into the request `options`
- use `llm.think`, not `llm.ollama.think`
- `ollama.options.temperature` is rejected because `grading.temperature` owns that setting

## `search`

The CLI reads a pre-fetched JSON results file:

```yaml
search:
  results_file: results.json
```

Library users can also pass the same query-to-results shape directly to `InMemoryResultsFetcher(...)`.

Supported result item fields for v1 are:

- `doc_id`
- `rank`
- `fields`

Anything you want the model to see should live under `fields`.

## `grading`

### Scale

Default scale is `0-3`.

If you customize the scale, provide labels for every score in the configured range.

This scale customization is available only in structured prompt mode, not in `prompt_file` mode.

### `domain_context`

Optional context injected into the default structured prompt.

Useful when the search domain is specialized.

This is not allowed in `prompt_file` mode.

### `max_workers`

Maximum concurrent grading workers. Usally keep local to 1 as system resources are limited to one model usually.

- hosted providers: often `4-10`
- local Ollama models: usually `1-2`

### `passes`

Number of grading passes per item.

### `temperature`

Sampling temperature for the model.

- `0` is the safest default for reproducible grading
- higher values allow more variation, but can reduce consistency across runs

### `max_attempts`

Total attempts per item before it is recorded as a failure.

Examples:

- `1`: try each item once, then use the failure log or rerun later. **default**.
- `2`: one retry after the first failure
- `3`: up to three total attempts

### `request_timeout`

Provider request timeout in seconds.

Local models may need larger values like `180-300`. Be sure to run a model suitable for your system to keep under 10 seconds per grading item.

### `response_mode`

One of:

- `text`
- `json_schema`

`text` is the default and recommended mode for the broadest compatibility.

Use `json_schema` when the provider route reliably supports structured output and you want stricter machine-readable responses.

Structured output is mainly a reliability feature for parsing and validation. Do not assume it improves grading quality by itself.

### `prompt`

Optional structured prompt overrides:

- `instructions`
- `output_instructions`

These work only in structured prompt mode.

### `prompt_file`

Optional path to a full custom prompt file.

Supported placeholders in this mode:

- `{query}`
- `{result_fields}`

No other placeholders are supported in `prompt_file` mode.

## `output`

### `path`

Where to write the canonical raw judgments JSON file.

This should be a `.json` path.

The CLI also writes a sidecar failure log next to it:

- `judgments.json`
- `judgments-failures.json`

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

CLI flags override config-file values for the curated runtime surface.

Typical pattern:

```bash
judgement-ai grade \
  --config judgement-ai.yaml \
  --model gpt-5.1 \
  --output judgments.json
```

Advanced provider passthrough stays in YAML config rather than expanding into many CLI flags.

## Recommended Starting Points

### Hosted OpenAI-compatible provider

```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-5.1
  provider: openai_compatible

grading:
  max_workers: 4
  passes: 1
  temperature: 0
  max_attempts: 1
  request_timeout: 60
  response_mode: text
```

### Local Ollama

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: null
  model: qwen3.5:9b
  provider: ollama
  think: false
  ollama:
    keep_alive: "15m"

grading:
  max_workers: 1
  passes: 1
  temperature: 0
  max_attempts: 1
  request_timeout: 300
  response_mode: text
```
