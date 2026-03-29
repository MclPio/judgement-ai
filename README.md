# judgement-ai

Automated AI-powered search relevance grading. Replace costly human experts with an LLM that produces judgment lists compatible with existing search evaluation pipelines.

## Status

This repository is scaffolded as a Python library first, with a thin CLI layer on top. The implementation plan, agent workflow, and delivery pipeline are documented in [AGENT.md](/Users/mclpio/repos/judgement-ai/AGENT.md) and [PIPELINE.md](/Users/mclpio/repos/judgement-ai/PIPELINE.md).

Prompt research for Milestone 1 is captured in [docs/prompt-research.md](/Users/mclpio/repos/judgement-ai/docs/prompt-research.md).
Validation operations are documented in [docs/validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md).

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
- Validation workflow against TREC-style benchmark data

## Validation

The repository now includes a hybrid validation framework under [validate](/Users/mclpio/repos/judgement-ai/validate):

- `smoke` for fast local verification
- `trec_dl_passage` for the general-search benchmark story
- `trec_product_search` for the product-search benchmark story

The checked-in benchmark files are currently starter scaffolds shaped like the final derived artifacts. They are useful for exercising the validation pipeline, but they are not yet publish-ready official TREC-derived subsets. README benchmark claims should remain pending until those scaffolds are replaced with real derived subsets and saved run artifacts are committed.

Runbook summary:

1. Rebuild `trec_dl_passage` from `ir-datasets`
2. Rebuild `trec_product_search` from Amazon ESCI source data
3. Replace scaffold benchmark datasets with the generated outputs
4. Run `smoke` against your OpenAI-compatible endpoint
5. Run `trec_dl_passage`
6. Run `trec_product_search`
7. Promote saved artifacts into `validate/published/`
8. Update README with actual observed metrics

See [docs/validation-runbook.md](/Users/mclpio/repos/judgement-ai/docs/validation-runbook.md) for the exact workflow and example commands.

## Not yet published

- No benchmark correlation numbers are published yet.
- No supplement-specific validation claim is made yet.
- The current validation datasets and published result files are placeholders/scaffolds for the full benchmark workflow.

## Current State

Implemented:

- prompt system with validation
- Elasticsearch and pre-fetched results fetchers
- LLM grading with retries, concurrency, and failure logging
- incremental JSON/CSV outputs and resume support
- CLI config loading and grade command
- hybrid validation framework for general search and product search

Pending before benchmark publication:

- replace scaffold benchmark subsets with real derived TREC subsets
- run canonical benchmarks with a real model
- commit saved benchmark artifacts
- update README with observed metrics
