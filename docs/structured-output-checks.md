# Structured Output Checks

## Purpose

Use this doc to check whether structured output failures come from:

- the provider
- the model
- the OpenAI-compatible API layer
- our request shape
- our response parsing

This is a manual troubleshooting guide for provider behavior outside the repo. It is especially useful before changing `judgement_ai/grader.py`.

## Recommendation Right Now

Treat `text` mode as the most reliable default until structured output proves stable across the providers we care about.

Keep structured output only if it gives a clear benefit:

- fewer parse failures in practice
- better consistency than text mode
- acceptable compatibility across target providers

If those checks fail, prefer simplifying the product and dropping or de-emphasizing structured output.

For Ollama specifically:

- keep support only if it is easy to maintain and materially improves results
- if it needs provider-specific workarounds that make the core grader harder to trust, it is probably not worth making central to the product

## What To Check

Run the same prompt in both modes:

1. plain text with strict `SCORE: <number>` output
2. structured JSON mode

Check the same model and provider in both cases.

Record:

- provider name
- model name
- exact date
- exact endpoint
- whether the request succeeded
- whether the response format matched what was requested
- whether the content was actually useful for grading

## Suggested Providers

Check at least:

- OpenAI-compatible provider you care about most
- OpenRouter chat interface or API path, if that is your current suspect
- Ollama, only if local-model support remains a real product goal

## Test Matrix

For each provider/model pair, check:

- text mode, temperature `0`
- structured mode, temperature `0`
- one short prompt
- one realistic grading prompt

If structured output fails, note whether it was:

- request rejected
- schema ignored
- malformed JSON returned
- response shape different than expected
- empty content
- extra prose wrapped around JSON
- transport or timeout issue

## Minimal Text Prompt

Use something like:

```text
You are grading search relevance on a 0-3 scale.

Query: vitamin b6

Result:
title: Vitamin B6 100mg
description: Supports energy metabolism

Explain briefly, then end with:
SCORE: <number>
```

Expected result:

- response succeeds
- the last line is `SCORE: <number>`

## Minimal Structured Prompt

Use something like:

```text
You are grading search relevance on a 0-3 scale.

Query: vitamin b6

Result:
title: Vitamin B6 100mg
description: Supports energy metabolism

Return JSON with:
- score: integer from 0 to 3
- reasoning: short string
```

Expected result:

- response succeeds
- output is valid JSON only
- `score` is an integer
- `reasoning` is a string

## OpenAI-Compatible Questions To Answer

When structured output fails, answer these before editing code:

1. Did the provider actually support JSON schema, or only JSON-like output?
2. Did the endpoint reject `response_format` or schema fields?
3. Did the model ignore the schema even though the API accepted it?
4. Did the provider wrap JSON in markdown or prose?
5. Did the response body differ from what `judgement-ai` expects today?

## Repo Follow-Up After Manual Checks

Once you have manual results, decide one of these paths:

### Path A. Keep Structured Output

Use this only if:

- at least one important OpenAI-compatible provider is reliable
- the implementation can be made simple
- the behavior is clearly better than text parsing

Then:

- keep `text` as fallback
- document provider caveats clearly
- add targeted tests around the observed response shapes

### Path B. Keep It As Best-Effort

Use this if:

- structured output works sometimes but is not dependable

Then:

- make text mode the recommended default
- position structured output as optional and provider-dependent
- avoid making the rest of the codebase more complex just to preserve it

### Path C. Remove It

Use this if:

- text mode is consistently more reliable
- structured mode adds more complexity than value

Then:

- remove `json_schema` support from the core workflow
- simplify docs, tests, and provider code

## Suggested Conclusion Standard

A good reason to keep structured output is:

- it reduces real failures for users

A weak reason to keep it is:

- it looks cleaner in theory

If text mode is more reliable for the providers users will actually use, prefer text mode.
