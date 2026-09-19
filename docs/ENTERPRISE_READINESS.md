# Enterprise Readiness — Audit and Evidence

**Commit under audit:** generated after the enterprise hardening pass
**Scope:** local runtime, API boundary, provider integration, RAG persistence,
security gates, CI and real MiniCPM5 execution.

## Current verified state

| Area | Evidence | Status |
|---|---|---|
| Unit/integration behavior | `pytest`: 50 passed, 3 subtests | PASS |
| Branch coverage | `pytest-cov`: 81.66% | PASS (threshold 80%) |
| Ruff | `ruff check` | PASS |
| Mypy | `mypy src` | PASS, 28 source files |
| Bandit | `bandit -q -r src -ll` | PASS |
| Dependency audit | `pip-audit . --format json` | PASS, project runtime has no known vulnerable dependency |
| Security baseline | `scripts/security_scan.py` | PASS, 0 findings |
| API process | Uvicorn real HTTP smoke | PASS: health, readiness, metrics, agent and RAG endpoints |
| API controls | JWT HS256 claims, request ID, bounded payloads | PASS in contract tests |
| Tenant/principal isolation | JWT-derived tenant/principal + retrieval filters | PASS in local contract tests |
| Rate limiting | fixed window, 429 and Retry-After | PASS in contract tests |
| RAG durability | SQLite WAL store + reload test | PASS |
| Provider protocol | OpenAI-compatible parser + retry + circuit breaker | PASS in fake-provider contract tests |
| Real MCP stdio subset | `initialize`, `tools/list`, `tools/call` over JSON-RPC | PASS: subprocess protocol test |
| Local MCP HTTPS | self-signed TLS + JWT per-tool scope | PASS: `evidence/security/mcp-http-tls.json` |
| Real local model | MiniCPM5-2B-Q8 at `127.0.0.1:8082` | PASS: real tool loop |
| Real FastEmbed | BGE-small ONNX vs hashing control | PASS: `evidence/benchmarks/embedding-comparison.json` |
| Adversarial FastEmbed | 54 semantic/distractor questions; abstention | PASS: `evidence/benchmarks/adversarial-embedding-comparison.json` |
| OpenTelemetry SDK | in-memory spans for HTTP/agent/provider/tool/RAG | PASS: contract tests |
| Local load/chaos | 100 concurrent requests + failure injection | PASS: `evidence/benchmarks/chaos-load.json` |
| Load curve | concurrency 1/10/25/50/100/200 | PASS: `evidence/benchmarks/load-curve.json` |
| Five-minute demo | JWT/RAG/RBAC/MCP/OTel flow | PASS: `evidence/demo/five-minute-demo.json` |
| Local benchmark | 100 agent/RAG runs with p50/p95 | PASS: evidence JSON |
| Docker execution | Docker daemon on current host | NOT EXECUTED: command unavailable |
| Hosted GitHub Actions | remote repository/run URL | NOT EXECUTED: no remote configured |
| Full external MCP deployment | hosted server/client and network isolation | NOT EXECUTED: local HTTPS boundary only |

## MiniCPM5 real-path evidence

The official profile launcher started the local router with:

```text
model: MiniCPM5-2B-Q8
endpoint: http://127.0.0.1:8082/v1
context: 98304
api key: local-only
```

The probe sent a real OpenAI-compatible request with `tool_choice=required`.
The observed loop was:

```text
provider request
→ MiniCPM5 tool call: calculator({"expression": "7 * 6"})
→ local calculator execution: 42.0
→ tool result returned to MiniCPM5
→ final answer: "The result of 7 * 6 is 42.0."
```

Measured result:

```text
status: completed
turns: 2
latency: 12.257931 seconds
prompt tokens: 383
completion tokens: 15
safety: ALLOW
trace: evidence/traces/minicpm5-tool-call.jsonl
report: evidence/provider/minicpm5-tool-call.json
```

This proves a real local-model tool loop. It does not prove that every model,
provider or external MCP server has the same capability.

## Enterprise controls added

- OpenAI-compatible provider adapter with timeout, retry policy and circuit breaker.
- Strict parsing of `finish_reason`, `tool_calls`, JSON arguments and usage.
- Tool JSON schemas with `additionalProperties=false`.
- Provider → tool → provider loop with bounded turns.
- Prompt-injection and PII safety gate before provider calls.
- SQLite WAL trace sink with explicit commit/rollback/close behavior.
- SQLite corpus store with transactional document/chunk reload.
- Minimal MCP stdio JSON-RPC subset with `initialize`, `tools/list` and
  `tools/call`, backed by the allowlisted registry.
- FastAPI health/readiness endpoints.
- Optional Bearer authentication for `/v1/*` routes.
- JWT HS256 authentication with issuer/audience/expiry/signature validation,
  derived tenant/principal claims and per-tool MCP scopes.
- Request ID propagation and Prometheus-compatible basic counters.
- OpenTelemetry SDK spans with in-memory evidence and optional console export.
- FastEmbed BGE-small ONNX backend with hashing control and Recall/MRR benchmark.
- Adversarial retrieval corpus with semantic paraphrases, distractors, typos,
  multilingual case and explicit no-answer abstention cases.
- Async load/chaos evidence for provider failures, malformed responses, hanging
  tools, SQLite locks and recovery.
- Local concurrency curve with P95 degradation recorded instead of a single
  unsupported RPS claim.
- Non-root Docker image, read-only compose service and healthcheck.
- Mypy, Bandit, coverage and project-scoped pip-audit gates.

## Claims safe for a CV

Use:

> Built an offline-first agent evaluation platform with a real OpenAI-compatible
> provider adapter, MiniCPM5 tool-calling validation, bounded retries and circuit
> breaking, structured tool schemas, safety/PII gates, JWT-derived tenant/scopes,
> FastAPI health/auth/metrics, SQLite-persisted RAG corpora, hybrid retrieval,
> FastEmbed benchmark, adversarial retrieval, OpenTelemetry spans, and 81.66% branch
> coverage and CI quality/security gates.

Do not claim yet:

- full production MCP server/client deployment with isolated workers;
- hosted GitHub Actions passing;
- Docker image passing in this environment;
- cloud deployment or Application Insights;
- persisted enterprise ACL authorization or compliance certification;
- Microsoft/Hugging Face/AWS credentials without account evidence.

## Remaining production promotion blockers

1. Obtain explicit repository publication scope, connect a real GitHub remote,
   enable branch protection and capture a hosted
   CI run URL.
2. Run Docker build/smoke/scan on a Docker-enabled runner.
3. Promote the local MCP HTTPS boundary to a full MCP client/server deployment
   with process/network isolation and external identity.
4. Add OpenTelemetry export, dashboards, alerts, SLOs and retention policy.
5. Add a production vector database, ACL/tenant filters and real documents.
6. Add an external secret manager, SBOM/signing and a clean locked dependency
   environment for every deploy target.
7. Perform independent threat modeling, distributed load testing and human
   release approval; local load/chaos evidence is already captured.

Until those items are verified, the project is **enterprise-grade in its local
engineering controls and evidence discipline**, but not a production service
approved for unrestricted enterprise traffic.
