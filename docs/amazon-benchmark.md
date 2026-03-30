# Amazon Benchmark

This repository now uses a single real benchmark source for validation: Amazon ESCI product-search data.

## Benchmark Definition

The canonical benchmark is derived locally from Amazon ESCI with these defaults:

- source: official Amazon ESCI files
- locale: `us`
- task view: reduced Task 1 (`small_version == 1`)
- sampling: deterministic per-label cap
- default benchmark size: about 200 rows (`50` rows per label by default)

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

## Why Smoke Exists

`smoke` stays in the repo because it answers a different question from the benchmark:

- does the endpoint respond?
- does the model follow the strict `SCORE:` format?
- do artifacts write correctly?

Always run `smoke` before the full Amazon benchmark when testing a new provider or local model.

## Metrics

Validation reports:

- Spearman correlation
- exact agreement

Artifacts include:

- raw judgments
- failures
- aligned human/AI rows
- summary metrics

## Local Data Policy

All benchmark data is local-only by default:

- raw downloads live under `validate/data/`
- derived benchmark JSON also lives under `validate/data/`
- these files are gitignored

The benchmark code and docs are committed, but the benchmark data itself is treated as operator-local working data.
