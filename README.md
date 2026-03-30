# judgement-ai

Automated AI-powered search relevance grading. Replace costly human experts with an LLM that produces judgment lists compatible with existing search evaluation pipelines.

## Status

This repository is scaffolded as a Python library first, with a thin CLI layer on top. The implementation plan, agent workflow, and delivery pipeline are documented in [AGENT.md](/Users/mclpio/repos/judgement-ai/AGENT.md) and [PIPELINE.md](/Users/mclpio/repos/judgement-ai/PIPELINE.md).

Prompt research for Milestone 1 is captured in [docs/prompt-research.md](/Users/mclpio/repos/judgement-ai/docs/prompt-research.md).
Validation operations are documented in [docs/validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md).
Benchmark details are documented in [docs/amazon-benchmark.md](/Users/mclpio/repos/judgement-ai/docs/amazon-benchmark.md).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

For validation work that computes benchmark metrics, install the optional validation extras:

```bash
pip install -e ".[dev,validate]"
```

## Planned package layout

```text
judgement_ai/
├── __init__.py
├── cli.py
├── config.py
├── fetcher.py
├── grader.py
├── output.py
├── prompts.py
└── resume.py
```

## Scope

- Python library first, CLI second
- Elasticsearch and pre-fetched file inputs for v1
- Quepid CSV and JSON outputs for v1
- Resumable grading runs
- Validation workflow against Amazon ESCI product-search data

## Validation

The repository now includes an Amazon-focused validation workflow under [validate](/Users/mclpio/repos/judgement-ai/validate):

- `smoke` for fast local verification
- `amazon_product_search` for the real benchmark

Benchmark data is now local-only by default. Raw Amazon downloads and the derived benchmark dataset live under `validate/data/` and are gitignored. The repo commits the benchmark code and docs, not the generated benchmark data.

Runbook summary:

1. Download Amazon ESCI data
2. Build the local `amazon_product_search` benchmark dataset
3. Run `smoke` against your OpenAI-compatible endpoint
4. Run `amazon_product_search`
5. Review saved artifacts and observed metrics

See [docs/validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md) for the exact workflow and example commands.

The runbook now includes both OpenRouter and Ollama examples. For local 8B models, start with `smoke` and use a small worker count before attempting the canonical benchmarks.
For slower local models, the recommended benchmark flow is a mostly single-pass run with `max_retries: 1`, followed by `--resume` or `--retry-failures` sweeps instead of burning time on inline retries.

## Not yet published

- No benchmark correlation numbers are published yet.
- No supplement-specific validation claim is made yet.
- The benchmark dataset is generated locally and not committed by default.

## Current State

Implemented:

- prompt system with validation
- Elasticsearch and pre-fetched results fetchers
- LLM grading with configurable retries, timeouts, concurrency, and failure logging
- incremental JSON/CSV outputs and resume support
- CLI config loading and grade command
- Amazon-only validation workflow plus smoke, progress reporting, and retry/resume recovery

Pending before benchmark publication:

- generate the Amazon benchmark locally
- run canonical benchmarks with a real model
- update README with observed metrics
