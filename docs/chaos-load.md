# Load and chaos evidence

**Command:** `PYTHONPATH=src python scripts/chaos_load.py --concurrency 100`

## Concurrency result

| Metric | Measured |
|---|---:|
| Concurrent requests | 100 |
| Successful responses | 100 |
| Success rate | 1.0 |
| Throughput | 293.9687 requests/s |
| Latency P50 | 321.6420 ms |
| Latency P95 | 328.4747 ms |

The load uses `asyncio` + `httpx` against the FastAPI ASGI application and is
not a claim about a distributed production cluster.

## Injected failures

| Case | Result |
|---|---|
| Provider timeout | `ProviderTimeout`, expected failure |
| Provider HTTP 429 | `ProviderError`, expected failure |
| Provider HTTP 500 | `ProviderError`, expected failure |
| Malformed provider JSON | `ProviderResponseError`, expected failure |
| Hanging tool | bounded `tool timed out after 0.020s` |
| SQLite write lock | `database is locked`, then counts recovered after release |
| Provider recovery | healthy response after breaker reset, recovered |

Raw machine-readable evidence is in
`evidence/benchmarks/chaos-load.json`.

### Boundary note

The tool timeout bounds the caller and cancels the future, but Python cannot
forcibly kill an already-running thread. A hostile or untrusted tool still needs
process/container isolation in the production deployment; this local test proves
the request path does not wait for the hanging handler.
