# TREC Product Search Provenance

This repository is designed to validate `judgement-ai` against a derived product-search benchmark subset.

Target upstream sources:

- Amazon Shopping Queries / ESCI source data
- Product metadata fields used for judging, such as title, brand, and description

Reference pages:

- https://www.amazon.science/code-and-datasets/shopping-queries-dataset-a-large-scale-esci-benchmark-for-improving-product-search

Current status:

- The checked-in `validate/datasets/trec_product_search.json` file is a starter scaffold for the validation pipeline.
- It matches the intended artifact shape for a real derived product-search subset, but it is not yet a publish-ready derived subset.
- Replace it with a real derived subset before publishing product-search benchmark claims.
- The intended derivation path is `validate/prepare_trec_product_search.py`, which uses Amazon ESCI source data.

Selection policy for the real subset:

- Use a medium-sized sample across multiple shopping/product queries.
- Stratify by relevance labels and preserve product metadata fields useful for judging.
- Preserve query id, query text, document id, and human labels.
- Preserve source rank when present, otherwise use deterministic source-order rank.
