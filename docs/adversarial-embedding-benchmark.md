# Adversarial embedding benchmark

The original lexical benchmark is preserved in
`evidence/benchmarks/embedding-comparison.json`. It intentionally saturated at
Recall/MRR 1.0 and is not used as semantic proof.

## Methodology

- 24 short documents, including near-duplicate distractors.
- 54 questions: 48 answerable and 6 explicitly unanswerable.
- Categories include paraphrase, synonyms, abbreviation, Portuguese/English,
  typo, distractor, scope, timeout and abstention.
- `vector_only` retrieval isolates embedding behavior from keyword fusion and
  reranker bonuses.
- Hashing remains the deterministic control.
- FastEmbed uses `BAAI/bge-small-en-v1.5` with 384 dimensions.

## Measured results

| Backend | Recall@1 | Recall@3 | Recall@5 | MRR | Abstention | False positive | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Hashing | 0.583333 | 0.729167 | 0.791667 | 0.655903 | 1.0 | 0.0 | 0.56525 ms | 1.0295 ms |
| FastEmbed | 0.770833 | 0.916667 | 0.9375 | 0.845486 | 1.0 | 0.0 | 5.40105 ms | 10.3248 ms |

FastEmbed improved absolute Recall@1 by `0.1875` and MRR by `0.189583` on
this adversarial set. That is a measured local result, not a universal claim
about all corpora or languages.

Resource measurements:

| Backend | Dimensions | Float32 index | RSS delta |
|---|---:|---:|---:|
| Hashing | 128 | 12,288 B | 118,784 B |
| FastEmbed | 384 | 36,864 B | 218,828,800 B |

The FastEmbed model cache was `67,181,330 B`. RSS is process-level and includes
ONNX runtime allocations. The BGE-small model is English; the one multilingual
case scored zero for both backends and is intentionally reported, not hidden.

The abstention fix also removed stopword-only evidence: unanswerable questions
returned `abstention_rate=1.0` and `false_positive_rate=0.0` for both backends.

## Reproduce

```bash
PYTHONPATH=src python scripts/adversarial_embedding_benchmark.py
```

Raw result and dataset:

```text
evidence/benchmarks/adversarial-embedding-comparison.json
evals/adversarial_dataset.json
```
