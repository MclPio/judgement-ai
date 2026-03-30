# Amazon Product Search Provenance

This repository validates `judgement-ai` against a locally derived Amazon ESCI benchmark.

Source:

- official Amazon ESCI files from the Amazon Science `esci-data` project

Default derivation behavior:

- locale: `us`
- task view: reduced Task 1 (`small_version == 1`)
- deterministic per-label cap
- local-only generated benchmark dataset under `validate/data/`

The benchmark data is intentionally not committed by default.
