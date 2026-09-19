# Embedding benchmark

**Dataset:** 100 deterministic documents / 50 golden questions
**Model:** `BAAI/bge-small-en-v1.5` via FastEmbed ONNX
**Run:** `scripts/embedding_benchmark.py --runs 50`
**Raw evidence:** `evidence/benchmarks/embedding-comparison.json`

| Backend | Dimensions | Recall@1 | Recall@3 | Recall@5 | MRR | P50 (ms) | P95 (ms) | Build (ms) | Float32 index | RSS delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hashing control | 128 | 1.0 | 1.0 | 1.0 | 1.0 | 2.52765 | 2.7132 | 5.4169 | 51,200 B | 487,424 B |
| FastEmbed BGE small | 384 | 1.0 | 1.0 | 1.0 | 1.0 | 9.4803 | 11.2412 | 3,118.2052 | 153,600 B | 392,331,264 B |

## Interpretation

The deterministic dataset is too lexically explicit to distinguish retrieval
quality: both backends reach perfect Recall/MRR. FastEmbed is nevertheless a
real local embedding backend with a 384-dimensional ONNX model and a measured
runtime cost. The hashing backend remains the fast control. A production choice
requires a harder, semantically ambiguous dataset before selecting a winner.

FastEmbed model cache size in this run:

```text
67,181,330 bytes
```

RSS is process-level Windows RSS measured with `psutil`, so it includes the
ONNX runtime/model allocation and should not be interpreted as a pure vector
index allocation. The explicit float32 index payload is reported separately.

The Windows symlink warning from Hugging Face is an environment/storage warning,
not a fabricated model pass; files were downloaded and the benchmark completed.
