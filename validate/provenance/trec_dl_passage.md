# TREC DL Passage Provenance

This repository is designed to validate `judgement-ai` against a derived subset of the TREC 2019 Deep Learning passage-ranking materials.

Target upstream sources:

- TREC 2019 Deep Learning passage test queries
- `msmarco-passagetest2019-top1000.tsv`
- `2019qrels-pass.txt`

Reference pages:

- https://microsoft.github.io/msmarco/TREC-Deep-Learning-2019.html
- https://trec.nist.gov/data/deep2019.html

Current status:

- The checked-in `validate/datasets/trec_dl_passage.json` file is a starter scaffold for the validation pipeline.
- It is intentionally small and shaped like the final derived artifact, but it is not yet a publish-ready official TREC-derived subset.
- Replace it with a real derived subset before publishing benchmark claims in the README.
- The intended derivation path is `validate/prepare_trec_dl_passage.py`, which uses `ir-datasets`.

Selection policy for the real subset:

- Use a medium-sized sample across multiple queries.
- Stratify by relevance labels `0`, `1`, `2`, `3`.
- Preserve query text, passage text, query id, document id, and human labels.
- Preserve source rank when available from the upstream dataset.
