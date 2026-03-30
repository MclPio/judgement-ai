# AGENT.md

## Purpose

This repository builds `judgement-ai`, a Python library and CLI for automated search relevance grading using LLMs. The agent working in this repo should optimize for shipping a trustworthy, dependency-light library with a thin CLI and a reproducible validation story.

## Product Constraints

- Library-first architecture. CLI is a wrapper, not the core.
- v1 supports Elasticsearch and pre-fetched JSON results only.
- v1 outputs Quepid-compatible CSV and generic JSON only.
- Temperature is always `0`.
- Fail loudly on grading format issues during core grading logic.
- Resume support and incremental writes are mandatory.
- Validation and credibility are first-class, not polish.

## Repo State

Current implementation status:

- Core library, CLI, retry logic, incremental outputs, resume, and validation scaffolding exist.
- Active validation modes are `smoke` and `amazon_product_search`.
- Benchmark data is intended to be generated locally under `validate/data/`, not committed by default.
- Local-model validation now favors a mostly single-pass first run with configurable timeout/retry settings, followed by resume or retry-only sweeps when needed.

This means:

- Do not present benchmark numbers as published facts unless they are backed by saved artifacts under `validate/published/`.
- Treat `validate/data/amazon_product_search.json` as local benchmark data, not repo-owned source.
- README benchmark claims must match saved summary artifacts exactly.
- Keep recovery behavior shared across the grader library, the main CLI, and the validation runner when improving long-running local workflows.

## Delivery Order

Work in this order unless the user explicitly redirects:

1. Prompt research and citation capture
2. Prompt design and placeholder validation
3. Fetchers
4. Grader orchestration and parsing
5. Output writers
6. Resume logic
7. CLI integration
8. Validation workflow
9. README and packaging polish

Do not jump ahead if the previous step is not working end-to-end.

## Working Rules

- Keep dependencies light. Prefer `requests`, `click`, `pyyaml`, and stdlib.
- Use small, explicit abstractions. Avoid framework-heavy designs.
- Write tests alongside implementation, not after.
- When behavior is safety-sensitive, prefer hard failure with actionable messaging.
- Preserve output compatibility with common evaluation pipelines.
- Prefer deterministic parsing and explicit schemas over clever heuristics.

## Implementation Expectations

- Every milestone should end with runnable tests.
- New public behavior should have at least one focused test.
- File formats should be documented with examples.
- User-facing errors should explain what failed and what to try next.
- README claims should only be made once code or validation exists.
- Validation claims should only be made once real benchmark datasets and saved published artifacts exist.

## Research Notes

Before implementing the grading prompt, capture sources and decisions from:

- Zheng et al. 2023, MT-Bench / Chatbot Arena judge guidance
- SIGIR 2024 TREC LLMJudge findings
- Databricks LLM auto-eval best practices

The differentiation is the pipeline and packaging, not novelty claims about the prompt itself.

## Definition Of Done

A milestone is complete only when:

- Code exists
- Tests pass
- The user-facing behavior is documented
- The next milestone can build on it without rework

For validation/data milestones, also require:

- provenance notes are updated
- scaffold-vs-published status is documented honestly
- any README metric matches committed saved output exactly
