# QA and Security Plan — Agent Engineering Sprint

**Status:** executable plan with current gates implemented
**Principle:** evidence is generated from commands and measured runs; no number is invented.

## 1. Test layers

| Layer | Location | Purpose | Gate |
|---|---|---|---|
| Unit/behavior | `tests/` | router, tools, approval, schema, retrieval behavior | required |
| Integration-style | `tests/` | orchestrator lifecycle and JSONL trace | required |
| Evaluation | `evals/` | golden routing, tool selection, schema recovery, RAG metrics | required |
| Static quality | Ruff + compileall | import/type/syntax hygiene | required |
| Security | `scripts/security_scan.py` | secrets, private keys, unsafe shell patterns | required |
| Runtime smoke | `production_rag.cli evaluate` | corpus and evaluator actually execute | required |
| Distribution | editable install + entry points | package is usable outside `PYTHONPATH` | verified locally |
| Container | `.github/workflows/docker.yml` | Docker build and smoke run | pending daemon |

## 2. Agent metrics

The evidence generator measures these from eight real offline runs:

- **Task success rate:** completed runs / total runs.
- **Tool selection accuracy:** expected tool matches / tool-expected cases.
- **Structured-output validity:** responses passing schema / total runs.
- **Retry rate:** runs with one or more retries / total runs.
- **Latency P50/P95:** measured run latency in milliseconds.
- **Token usage:** sum of deterministic input/output estimates in traces.
- **Error rate:** failed terminal runs / total runs.

Current artifact: `evidence/metrics/agent_metrics.json`.

## 3. RAG metrics

The evaluator uses 100 generated documents and 50 golden questions. For each
variant it calculates:

- Recall@1, Recall@3 and Recall@5;
- Mean Reciprocal Rank;
- groundedness from expected terms in retrieved context;
- answer relevance from lexical overlap with the query.

Variants are evaluated against the same dataset:

1. vector-only;
2. hybrid vector + keyword with RRF;
3. hybrid plus reranker.

Current artifact: `evidence/eval-results/rag_metrics.json`.

## 4. MCP-style threat model

| ID | Threat | STRIDE | Severity | Required control | Test/evidence |
|---|---|---|---|---|---|
| TM-001 | unknown tool tries to execute | Elevation | high | allowlisted registry | `test_unknown_tool...` |
| TM-002 | dunder argument crosses boundary | Tampering | medium | reject unsafe keys | tool boundary test |
| TM-003 | tool output replaces system instructions | Tampering / disclosure | high | marker detection and block | `test_tool_output_injection...` |
| TM-004 | calculator becomes code execution | Elevation | high | AST allowlist, no `eval` | malformed/unsafe expression test |
| TM-005 | trace leaks secret-like values | Disclosure | high | redaction and no credentials in fixtures | source scan + trace review |
| TM-006 | retry repeats non-idempotent side effect | DoS / Elevation | medium | bounded retries and approval | approval tests + retry metric |
| TM-007 | RAG answers without evidence | Disclosure | medium | no-evidence fallback and citations | RAG answer test |
| TM-008 | hard-coded secret enters repository | Disclosure | high | static security gate | `security_scan.py` |

## 5. Release gates

A local release is eligible only if all are true:

- [ ] `python -m compileall -q src evals tests scripts` passes;
- [ ] `python -m ruff check src tests evals scripts` passes;
- [ ] unit test discovery passes;
- [ ] eval discovery passes;
- [ ] security scan returns `status=pass` and `findings=[]`;
- [ ] RAG smoke returns 100 documents and 50 questions;
- [ ] evidence files include command provenance;
- [ ] `git diff --check` is clean;
- [ ] external credentials are either proven by the user or labeled pending;
- [ ] Docker/GitHub status is labeled according to actual environment.

The executable aggregate is `python scripts/ci.py --strict`.

## 6. Evidence rules

- Store measured output under `evidence/`; retain the command or code path that
  generated it.
- Keep deterministic baseline metrics separate from future provider metrics.
- Do not write “GitHub Actions passing” unless a hosted run URL/check is present.
- Do not write “Docker passing” when only a Dockerfile was inspected.
- Do not publish Microsoft, Hugging Face or AWS credentials before the account
  shows the credential.
- Preserve trace samples only when they contain no secrets; the committed sample
  is `evidence/traces/agent-matrix.jsonl`.

## 7. Files NOT touched by this plan author

This plan defines QA/security gates and does not own production or workflow
implementation. The following paths remain outside its write scope:

| Path | Reason |
|---|---|
| `src/` | implementation owned by the coding pass |
| `tests/` | test implementation owned by the coding pass |
| `evals/` | evaluator implementation owned by the coding pass |
| `.github/` | hosted workflow implementation owned by delivery |
| `README.md` | public claims updated only from measured evidence |
| `pyproject.toml` | packaging contract owned by delivery |

## 8. Current status boundary

The local gates are verified. Docker is not installed on the current host and
there is no GitHub remote, so container execution and hosted Actions remain
pending environment setup. That is a documented blocker, not a simulated pass.
