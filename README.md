# judgement-ai

<img width="1440" height="480" alt="ARC-26106-2201-3x1" src="https://github.com/user-attachments/assets/a7fb4e37-3282-48fe-8f1e-898c3ebd165c" />

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

- grades `(query, document)` pairs with an OpenAI-compatible or Ollama-backed model
- supports file-backed and in-memory result inputs
- writes canonical raw judgments JSON, with optional CSV export
- supports preview, retries, resume, and sidecar failure logs

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
  --queries examples/queries.txt \
  --results-file examples/results.json \
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
  --queries examples/queries.txt \
  --results-file examples/results.json \
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

## Capabilities

The current shipped surface includes:

- `judgement-ai grade`
- `judgement-ai preview`
- `judgement-ai export-csv`
- structured prompt mode and full `prompt_file` mode
- OpenAI-compatible and Ollama provider paths
- canonical raw judgments JSON, optional CSV export, retries, resume, and failure logs

Config-driven runs can be one command when the config includes queries, search input, and output paths:

```bash
judgement-ai grade --config judgement-ai.yaml
```

## Where To Look Next

- [examples/README.md](examples/README.md): runnable examples for CLI and library usage
- [docs/judgement-ai.yaml.example](docs/judgement-ai.yaml.example): minimal config starting point
- [docs/configuration.md](docs/configuration.md): config and behavior reference

## License

This project is licensed under the [MIT License](LICENSE).

## Documentation

User-facing docs:

- [README.md](README.md)
- [examples/README.md](examples/README.md)
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
