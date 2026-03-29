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

