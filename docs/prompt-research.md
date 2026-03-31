# Prompt Research

## Goal

Capture the research-backed prompt decisions for `judgement-ai` before implementing live grading.

## Sources

1. Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (2023)
   Source: [arXiv / paper index](https://huggingface.co/papers/2306.05685)
2. Rahmani et al., *LLMJudge: LLMs for Relevance Judgments* (LLM4Eval at SIGIR 2024)
   Source: [preprint / DOI landing page](https://doi.org/10.48550/arXiv.2408.08896)
3. Thomas et al., *Large Language Models can Accurately Predict Searcher Preferences* (SIGIR 2024)
   Source: [Microsoft Research PDF](https://www.microsoft.com/en-us/research/uploads/prod/2023/09/LLMs_for_relevance_labelling__SIGIR_24_-2.pdf)
4. Databricks / MLflow judge guidance
   Sources:
   - [Scorers and LLM judges](https://docs.databricks.com/gcp/en/mlflow3/genai/eval-monitor/concepts/scorers)
   - [Create a guidelines LLM judge](https://learn.microsoft.com/en-us/azure/databricks/mlflow3/genai/eval-monitor/concepts/judges/guidelines)

## What The Sources Say

### 1. Strong prompts matter a lot

Thomas et al. report that LLM performance "varies with prompt features" and also "varies unpredictably with simple paraphrases." Their experiments show prompt structure materially changes agreement with human labels. They also report that temperature was set to zero for reproducibility in their experiments.

Implication for this repo:

- We should treat prompt design as a first-class implementation milestone.
- We should default temperature to `0` for reproducibility, while leaving room for a user override if needed.
- We should validate user-supplied prompt templates before making any LLM calls.

### 2. Structured judgment instructions improve reliability

Thomas et al. evaluate prompts built from explicit instructions, optional description/narrative fields, and explicit aspects. In their reported results, adding aspect-oriented guidance improved agreement more than several other prompt features.

Implication for this repo:

- Use explicit, concrete grading instructions.
- Keep scale labels textual, not numeric-only.
- Leave room for domain context because search relevance depends on the corpus and task.

### 3. Small, labeled relevance scales are standard in IR judging

The SIGIR 2024 `LLMJudge` challenge uses a four-point relevance scale:

- `3` perfectly relevant
- `2` highly relevant
- `1` related
- `0` irrelevant

That is a close fit for the proposed `0-3` default in `judgement-ai`.

Implication for this repo:

- Default to a `0-3` labeled scale.
- Require complete labels when users choose a custom range.

### 4. Judges should operate on explicit context and explicit criteria

Databricks guidance emphasizes that LLM judges receive context as structured input, apply natural-language criteria, and return a judgment with rationale. The docs also stress interpretable criteria and fast iteration over guideline wording.

Implication for this repo:

- Build prompt text from explicit query + result fields + scale labels + optional domain context.
- Keep prompt rendering deterministic so prompt changes are reviewable.
- Preserve a path for custom prompt templates.

### 5. LLM-as-a-judge is useful, but biases are real

Zheng et al. highlight position bias, verbosity bias, and limited reasoning ability as recurring issues for LLM judges. Their overall conclusion is positive, but not "prompt anything and trust it."

Implication for this repo:

- Document bias risks in README later.
- Keep parsing strict and outputs auditable.
- Prefer prompts that ask for explicit reasoning before the final score.

## Prompt Decisions For `judgement-ai`

These are the implementation decisions we are adopting now:

1. Default scale is `0-3` with textual labels.
2. Prompt must contain `{query}`, `{result_fields}`, and `{scale_labels}`.
3. `{domain_context}` is optional but supported by the default prompt.
4. The default prompt asks for brief reasoning followed by a strict `SCORE: <number>` line.
5. Prompt rendering is deterministic so tests can lock behavior down.
6. Custom scales must provide labels for every score in the configured range.

## Notes On Evidence Strength

- The requirement to ask for reasoning before the score is supported directionally by LLM-as-judge literature and by the broader practice of using explanation-oriented judge prompts. In this repo we are adopting it as a design choice informed by those sources, not claiming any single paper proves this exact prompt is universally optimal.
- We should still validate the final prompt empirically during the TREC benchmark phase rather than relying on literature alone.
