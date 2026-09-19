# Local load curve

**Command:** `PYTHONPATH=src python scripts/load_curve.py`

The harness uses `asyncio` + `httpx` against FastAPI `ASGITransport`. It is a
local concurrency curve, not a production capacity or distributed benchmark.

| Concurrency | Throughput (req/s) | P50 | P95 | Success | Error |
|---:|---:|---:|---:|---:|---:|
| 1 | 95.9702 | 10.3327 ms | 10.3327 ms | 1.0 | 0.0 |
| 10 | 289.3359 | 32.8871 ms | 33.7912 ms | 1.0 | 0.0 |
| 25 | 297.9024 | 80.5669 ms | 81.9895 ms | 1.0 | 0.0 |
| 50 | 294.0988 | 163.04595 ms | 166.1974 ms | 1.0 | 0.0 |
| 100 | 286.1293 | 335.75515 ms | 342.0853 ms | 1.0 | 0.0 |
| 200 | 288.4440 | 665.39555 ms | 677.4062 ms | 1.0 | 0.0 |

The observable degradation is tail latency: P95 grows from `10.3327 ms` at
concurrency 1 to `677.4062 ms` at concurrency 200. Throughput is not monotonic
because this is an in-process ASGI harness with per-request client creation.

Raw evidence:

```text
evidence/benchmarks/load-curve.json
```
