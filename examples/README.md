# Examples

This folder is the shortest path to the current shipped workflows.

## Start Here

Use these sample inputs for local experimentation:

- [queries.txt](/Users/mclpio/repos/judgement-ai/examples/queries.txt)
- [results.json](/Users/mclpio/repos/judgement-ai/examples/results.json)

## CLI Flows

### 1. Preview config and prompt shape

```bash
judgement-ai preview --config examples/openai-config.yaml
```

Use this first when you want to confirm prompt mode, provider resolution, response mode, and request payload shape without making provider calls.

### 2. Grade with an OpenAI-compatible provider

```bash
judgement-ai grade --config examples/openai-config.yaml
```

This uses:

- [openai-config.yaml](/Users/mclpio/repos/judgement-ai/examples/openai-config.yaml)
- [queries.txt](/Users/mclpio/repos/judgement-ai/examples/queries.txt)
- [results.json](/Users/mclpio/repos/judgement-ai/examples/results.json)

### 3. Resume a partial run

```bash
judgement-ai grade --config examples/openai-config.yaml --resume
```

### 4. Export CSV later from the canonical JSON artifact

```bash
judgement-ai export-csv \
  --input judgments.json \
  --output judgments.csv
```

### 5. Grade with a local Ollama model

```bash
judgement-ai grade --config examples/ollama-config.yaml
```

This uses:

- [ollama-config.yaml](/Users/mclpio/repos/judgement-ai/examples/ollama-config.yaml)

### 6. Full custom prompt-file mode

`openai-config.yaml` includes the structured prompt mode. To switch to full prompt ownership, point `grading.prompt_file` at:

- [custom_prompt_template.txt](/Users/mclpio/repos/judgement-ai/examples/custom_prompt_template.txt)

That mode supports only:

- `{query}`
- `{result_fields}`

## Library Flows

- [prefetched_example.py](/Users/mclpio/repos/judgement-ai/examples/prefetched_example.py): file-backed results with `FileResultsFetcher`
- [in_memory_example.py](/Users/mclpio/repos/judgement-ai/examples/in_memory_example.py): in-memory results with `InMemoryResultsFetcher`
- [ollama_example.py](/Users/mclpio/repos/judgement-ai/examples/ollama_example.py): direct library usage against Ollama