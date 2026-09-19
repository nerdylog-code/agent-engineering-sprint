# Enterprise Readiness — Audit and Evidence

**Commit under audit:** generated after the enterprise hardening pass
**Scope:** local runtime, API boundary, provider integration, RAG persistence,
security gates, CI and real MiniCPM5 execution.

## Current verified state

| Area | Evidence | Status |
|---|---|---|
| Unit/integration behavior | `pytest`: 34 passed, 3 subtests | PASS |
| Branch coverage | `pytest-cov`: 80.42% | PASS (threshold 80%) |
| Ruff | `ruff check` | PASS |
| Mypy | `mypy src` | PASS, 23 source files |
| Bandit | `bandit -q -r src -ll` | PASS |
| Dependency audit | `pip-audit . --format json` | PASS, project runtime has no known vulnerable dependency |
| Security baseline | `scripts/security_scan.py` | PASS, 0 findings |
| API process | Uvicorn real HTTP smoke | PASS: health, readiness, metrics, agent and RAG endpoints |
| API controls | optional Bearer token, request ID, bounded payloads | PASS in contract tests |
| RAG durability | SQLite WAL store + reload test | PASS |
| Provider protocol | OpenAI-compatible parser + retry + circuit breaker | PASS in fake-provider contract tests |
| Real MCP stdio subset | `initialize`, `tools/list`, `tools/call` over JSON-RPC | PASS: subprocess protocol test |
| Real local model | MiniCPM5-2B-Q8 at `127.0.0.1:8082` | PASS: real tool loop |
| Docker execution | Docker daemon on current host | NOT EXECUTED: command unavailable |
| Hosted GitHub Actions | remote repository/run URL | NOT EXECUTED: no remote configured |
| Real MCP transport | MCP client/server/auth boundary | NOT YET IMPLEMENTED |

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
- Request ID propagation and Prometheus-compatible basic counters.
- Non-root Docker image, read-only compose service and healthcheck.
- Mypy, Bandit, coverage and project-scoped pip-audit gates.

## Claims safe for a CV

Use:

> Built an offline-first agent evaluation platform with a real OpenAI-compatible
> provider adapter, MiniCPM5 tool-calling validation, bounded retries and circuit
> breaking, structured tool schemas, safety/PII gates, FastAPI health/auth/
> metrics, SQLite-persisted RAG corpora, hybrid retrieval, reranking, 80.42% branch
> coverage and CI quality/security gates.

Do not claim yet:

- full production MCP server/client deployment;
- hosted GitHub Actions passing;
- Docker image passing in this environment;
- cloud deployment or Application Insights;
- multi-tenant authorization or compliance certification;
- Microsoft/Hugging Face/AWS credentials without account evidence.

## Remaining production promotion blockers

1. Connect a real GitHub remote, enable branch protection and capture a hosted
   CI run URL.
2. Run Docker build/smoke/scan on a Docker-enabled runner.
3. Expand the stdio MCP subset to a full MCP client/server deployment with
   authentication, per-tool scopes and process/network isolation.
4. Add OpenTelemetry export, dashboards, alerts, SLOs and retention policy.
5. Add a production vector database, ACL/tenant filters and real documents.
6. Add an external secret manager, SBOM/signing and a clean locked dependency
   environment for every deploy target.
7. Perform independent threat modeling, load testing, chaos/recovery testing and
   human release approval.

Until those items are verified, the project is **enterprise-grade in its local
engineering controls and evidence discipline**, but not a production service
approved for unrestricted enterprise traffic.
