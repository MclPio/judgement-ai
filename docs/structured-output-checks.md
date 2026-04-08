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
- better output-format consistency than text mode
- acceptable compatibility across target providers

If those checks fail, prefer simplifying the product and dropping or de-emphasizing structured output.

For Ollama specifically:

- keep support only if it is easy to maintain and materially improves results
- if it needs provider-specific workarounds that make the core grader harder to trust, it is probably not worth making central to the product

Current project stance:

- `text` is the default and recommended mode
- `json_schema` remains supported as an optional provider-dependent mode
- structured output should be treated as an output-reliability feature, not evidence of better grading quality

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

## Terminal Procedure

Run these checks from the repo root.

Setup:

```bash
source .venv/bin/activate
```

You only need one provider at a time:

```bash
export OPENROUTER_API_KEY="..."
export OLLAMA_MODEL="qwen3.5:latest"
export OPENROUTER_MODEL="openai/gpt-4.1-mini"
```

## Smoke Dataset Inputs

Use these rows from `validate/datasets/smoke.json`:

```text
Query: vitamin b6
Result title: Vitamin B6 100mg Capsules
Result description: A supplement where vitamin B6 is the primary ingredient.
Expected human score: 3
```

```text
Query: vitamin b6
Result title: Ceramic Coffee Mug
Result description: A kitchen mug unrelated to supplements or vitamins.
Expected human score: 0
```

```text
Query: magnesium for sleep
Result title: Magnesium Glycinate
Result description: Often used by customers looking for nighttime magnesium support.
Expected human score: 2
```

## Shared Prompt And Schema

Define these once in your shell:

```bash
PROMPT_TEXT=$(cat <<'EOF'
You are a search relevance expert.

Your task is to grade how relevant the following search result is to the query.

Use this scale:
0: Completely irrelevant - the result has no connection to the query.
1: Related but not relevant - the result shares a topic but does not address the query intent.
2: Relevant - the result addresses the query but is not the best possible result.
3: Perfectly relevant - the result directly and completely addresses the query intent.

First, write 2-3 sentences explaining your reasoning.
Then output your score on a new line in exactly this format:
SCORE: <number>

Query: vitamin b6

Result:
title: Vitamin B6 100mg Capsules
description: A supplement where vitamin B6 is the primary ingredient.
EOF
)

PROMPT_JSON=$(cat <<'EOF'
You are a search relevance expert.

Your task is to grade how relevant the following search result is to the query.

Use this scale:
0: Completely irrelevant - the result has no connection to the query.
1: Related but not relevant - the result shares a topic but does not address the query intent.
2: Relevant - the result addresses the query but is not the best possible result.
3: Perfectly relevant - the result directly and completely addresses the query intent.

Respond with JSON only.

Query: vitamin b6

Result:
title: Vitamin B6 100mg Capsules
description: A supplement where vitamin B6 is the primary ingredient.
EOF
)

SCHEMA=$(cat <<'EOF'
{
  "type": "object",
  "properties": {
    "score": { "type": "integer", "minimum": 0, "maximum": 3 },
    "reasoning": { "type": "string" }
  },
  "required": ["score", "reasoning"],
  "additionalProperties": false
}
EOF
)
```

Repeat the same commands with the other two smoke rows by replacing the query/result text in `PROMPT_TEXT` and `PROMPT_JSON`.

## OpenRouter Or Other OpenAI-Compatible API

### 1. Text Mode

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg model "$OPENROUTER_MODEL" \
    --arg prompt "$PROMPT_TEXT" \
    '{
      model: $model,
      temperature: 0,
      messages: [{role: "user", content: $prompt}]
    }')"
```

Expected:

- request succeeds
- output is normal text
- last line is `SCORE: <number>`

### 2. Strict JSON Schema Mode

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg model "$OPENROUTER_MODEL" \
    --arg prompt "$PROMPT_JSON" \
    --argjson schema "$SCHEMA" \
    '{
      model: $model,
      temperature: 0,
      messages: [{role: "user", content: $prompt}],
      response_format: {
        type: "json_schema",
        json_schema: {
          name: "judgement_ai_grade_result",
          strict: true,
          schema: $schema
        }
      }
    }')"
```

Expected:

- request succeeds
- output content is valid JSON only
- JSON has `score` and `reasoning`

### 3. Optional JSON Object Check

Use this if `json_schema` fails but you want to see whether weaker structured output still works:

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg model "$OPENROUTER_MODEL" \
    --arg prompt "$PROMPT_JSON" \
    '{
      model: $model,
      temperature: 0,
      messages: [{role: "user", content: $prompt}],
      response_format: {type: "json_object"}
    }')"
```

This mode is not implemented in the repo yet, but it is useful evidence for M2.

## Ollama

### 1. Text Mode

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg model "$OLLAMA_MODEL" \
    --arg prompt "$PROMPT_TEXT" \
    '{
      model: $model,
      messages: [{role: "user", content: $prompt}],
      stream: false,
      options: {temperature: 0}
    }')"
```

### 2. Structured Output Mode

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg model "$OLLAMA_MODEL" \
    --arg prompt "$PROMPT_JSON" \
    --argjson schema "$SCHEMA" \
    '{
      model: $model,
      messages: [{role: "user", content: $prompt}],
      stream: false,
      think: false,
      options: {temperature: 0},
      format: $schema
    }')"
```

Expected:

- request succeeds
- `message.content` is valid JSON only
- JSON has `score` and `reasoning`

## Optional Repo Check

If provider-direct checks work, compare with `judgement-ai`.

Create a tiny local input:

```bash
cat > /tmp/structured-check-results.json <<'EOF'
{
  "vitamin b6": [
    {
      "doc_id": "smoke-doc-1",
      "rank": 1,
      "fields": {
        "title": "Vitamin B6 100mg Capsules",
        "description": "A supplement where vitamin B6 is the primary ingredient."
      }
    }
  ]
}
EOF

printf "vitamin b6\n" > /tmp/structured-check-queries.txt
```

Text mode:

```bash
source .venv/bin/activate && judgement-ai grade \
  --queries /tmp/structured-check-queries.txt \
  --results-file /tmp/structured-check-results.json \
  --model "$OPENROUTER_MODEL" \
  --base-url https://openrouter.ai/api/v1 \
  --api-key "$OPENROUTER_API_KEY" \
  --response-mode text \
  --output /tmp/structured-check-text.json \
  --force
```

Structured mode:

```bash
source .venv/bin/activate && judgement-ai grade \
  --queries /tmp/structured-check-queries.txt \
  --results-file /tmp/structured-check-results.json \
  --model "$OPENROUTER_MODEL" \
  --base-url https://openrouter.ai/api/v1 \
  --api-key "$OPENROUTER_API_KEY" \
  --response-mode json_schema \
  --output /tmp/structured-check-json.json \
  --force
```

If provider-direct works but the repo run fails, that points to our request shape, response handling, or parse expectations.

## What To Paste Back

For each provider/model pair, paste back:

```text
Provider:
Model:
Endpoint:

TEXT MODE:
- success/failure:
- raw output:

JSON_SCHEMA MODE:
- success/failure:
- raw output:

JSON_OBJECT MODE (if tested):
- success/failure:
- raw output:

Notes:
- Did the provider reject the request?
- Did it return prose around JSON?
- Was text mode more reliable?
- Did repo behavior differ from direct API behavior?
```

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
