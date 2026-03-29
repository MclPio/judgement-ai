# TREC Product Search Provenance

This repository is designed to validate `judgement-ai` against a derived subset of the TREC Product Search benchmark.

Target upstream sources:

- TREC 2023 Product Search topics
- TREC 2023 Product Search qrels
- TREC Product Search corpus or metadata-enhanced product records

Reference pages:

- https://trec.nist.gov/data/product2023.html
- https://trec.nist.gov/pubs/trec32/papers/trackorg.P.pdf
- https://www.amazon.science/code-and-datasets/shopping-queries-dataset-a-large-scale-esci-benchmark-for-improving-product-search

Current status:

- The checked-in `validate/datasets/trec_product_search.json` file is a starter scaffold for the validation pipeline.
- It matches the intended artifact shape for a real derived product-search subset, but it is not yet a publish-ready official TREC-derived subset.
- Replace it with a real derived subset before publishing product-search benchmark claims.

Selection policy for the real subset:

- Use a medium-sized sample across multiple shopping/product queries.
- Stratify by relevance labels and preserve product metadata fields useful for judging.
- Preserve query id, query text, document id, and human labels.
