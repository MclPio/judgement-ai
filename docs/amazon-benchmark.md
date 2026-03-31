# Amazon Benchmark

This repository now uses a single real benchmark source for validation: Amazon ESCI product-search data.

## Benchmark Definition

The canonical benchmark is derived locally from Amazon ESCI with these defaults:

- source: official Amazon ESCI files
- locale: `us`
- task view: reduced Task 1 (`small_version == 1`)
- sampling: deterministic round-robin by query within each label
- default benchmark size: about 200 rows (`50` rows per label by default)
- calibration slice size: 48 rows (`12` rows per label by default)

The benchmark keeps:

- query text
- product id
- rank when available
- human label mapped to the internal relevance scale
- product metadata useful for judging, such as title, brand, and description

## Label Mapping

Amazon ESCI labels are mapped to the validation relevance scale as:

- `E` -> `3`
- `S` -> `2`
- `C` -> `1`
- `I` -> `0`

This preserves a simple four-level relevance benchmark for local model validation.

## Sampling Policy

The benchmark keeps deterministic sampling, but avoids taking the first `N` rows per label after a plain sort.

Current derivation policy:

- group by human label
- within each label, group rows by query
- sort queries by `query_id`
- sort rows within each query by `rank`, then `doc_id`
- select one row per query per pass until the label cap is reached

This keeps the slice reproducible while reducing query concentration compared with a simple first-`N` sampler.

The prep script also writes:

- `amazon_product_search_report.json`
- `amazon_product_search_calibration.json`

The report captures query concentration and field coverage so you can inspect the slice before benchmarking.

## Judge Semantics

Validation against this benchmark should use ESCI-aware judging semantics rather than a generic IR relevance prompt.

In practice this means:

- complements are not substitutes
- hard constraints like `without`, capacity, quantity, material, and compatibility matter
- explicit brand constraints matter
- price ceilings like `$5 items` are real constraints
- short or ambiguous queries should be judged conservatively
- a single token or letter should not be over-expanded into a broad shopping intent

## Why Smoke Exists

`smoke` stays in the repo because it answers a different question from the benchmark:

- does the endpoint respond?
- does the model or provider honor the structured-output contract?
- do artifacts write correctly?

Always run `smoke`, then the calibration slice, before the full Amazon benchmark when testing a new provider or local model.

## Metrics

Validation reports:

- Spearman correlation
- exact agreement

Artifacts include:

- raw judgments
- failures
- aligned human/AI rows
- summary metrics
- analysis reports
- calibration gate files for local and reference runs

## Local Data Policy

All benchmark data is local-only by default:

- raw downloads live under `validate/data/`
- derived benchmark JSON also lives under `validate/data/`
- these files are gitignored

The benchmark code and docs are committed, but the benchmark data itself is treated as operator-local working data.
