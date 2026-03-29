# judgement-ai

Automated AI-powered search relevance grading. Replace costly human experts with an LLM that produces judgment lists compatible with existing search evaluation pipelines.

## Status

This repository is scaffolded as a Python library first, with a thin CLI layer on top. The implementation plan, agent workflow, and delivery pipeline are documented in [AGENT.md](/Users/mclpio/repos/judgement-ai/AGENT.md) and [PIPELINE.md](/Users/mclpio/repos/judgement-ai/PIPELINE.md).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
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

## Not yet implemented

The repository currently contains the project skeleton, process docs, module stubs, and basic tests so we can build iteratively in a disciplined way.

