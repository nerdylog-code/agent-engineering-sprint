# Context Manifest — Agent Engineering Sprint

**Status:** active
**Owner:** Rise / Investigation Team
**Date:** 2026-09-19
**Scope:** isolated, local-first implementation of the attached Agents + CI/CD + Evals + Observability + RAG + MCP study sprint.

## Why this project exists

The current workspace contains `hermes-local-control`, while the attached plan refers to a Meta-Harness and a Production RAG Lab. This project is intentionally isolated so existing projects with uncommitted changes are not modified.

## Acceptance criteria

1. A runnable Python package exposes deterministic agent routing, bounded retries, structured output validation, human approval, MCP-style tools, and JSONL traces.
2. A Production RAG Lab supports ingestion, chunking, deterministic local embeddings, vector + keyword hybrid retrieval, reciprocal-rank fusion, reranking, citations, and measured retrieval metrics.
3. `evals/` contains a golden dataset plus executable evals for routing, tools, structured output, agent quality, and RAG retrieval.
4. Local CI runs tests, lint/compile checks, security checks, integration tests, and emits measured evidence; Docker build instructions are reproducible when Docker is available.
5. Documentation explains architecture, decisions, interview questions, knowledge matrix, threat model, and exact evidence boundaries.
6. No external credential, Microsoft Applied Skill, Hugging Face certificate, AWS badge, or GitHub-hosted run is claimed as completed without user/account evidence.

## Current → target mapping

| Current concept | Target artifact | Action |
|---|---|---|
| Plan mentions Meta-Harness | `src/agent_lab/` | implement a dependency-light local harness |
| Agent request → trace | `src/agent_lab/orchestrator.py` + `src/agent_lab/tracing.py` | implement and test |
| Router/tool/structured output evals | `evals/` | implement deterministic measured suite |
| Production RAG architecture | `src/production_rag/` | implement hybrid retrieval and citations |
| CI/CD chain | `.github/workflows/` + `scripts/ci.py` | implement local and GitHub workflows |
| Portfolio proof | `evidence/` + README | generate only from real execution |
| Courses and credentials | `docs/credential-checklist.md` | leave as human-required, not fabricated |

## Safety and rollback

- Existing `D:/Hermes/ErisWorkspace/hermes-local-control` was backed up before this project was created.
- No existing repository is edited by this project.
- External network, cloud accounts, paid APIs, and credential forms are out of scope for automatic execution.
- The default runtime is deterministic and offline; optional integrations must be explicit.

## Missing context / explicit limits

- No GitHub remote is configured for the current workspace, so GitHub Actions cannot be executed remotely here.
- Microsoft, DeepLearning.AI, LangChain Academy, Hugging Face, and AWS course completion requires the user’s identity and interactive account access.
- Docker availability is checked during verification; if unavailable, the Dockerfile is statically linted and the result is labeled honestly.

## Quality gates

- `python -m unittest discover -s tests -v`
- `python -m compileall -q src evals tests scripts`
- `python scripts/ci.py`
- `python -m agent_lab.cli demo --json`
- `python -m production_rag.cli evaluate --json`
- security scan must report no hard-coded secrets and no unsafe subprocess/network use in the new source
- evidence files must contain measured values and command provenance

## Phase 2 — public proof acceptance criteria

- Add a deterministic adversarial retrieval dataset with paraphrase, synonym,
  abbreviation, multilingual, typo, near-duplicate, distractor and abstention cases.
- Compare hashing control versus FastEmbed using Recall@1/3/5, MRR, P50/P95,
  index payload size and measurable RSS.
- Add a load curve for concurrency 1, 10, 25, 50, 100 and 200 with throughput,
  success/error rate, P50 and P95.
- Update README for a five-minute demo and clearly separate local proof from
  externally unverified capabilities.
- Do not claim GitHub, Docker, Qdrant server, hosted OTel or cloud execution
  without real external execution.

## Phase 2 — current verified baseline and mapping

- Commit baseline: `40b2c92`.
- Current baseline: 48 pytest tests including 3 subtests; 81.41% branch coverage.
- FastEmbed BGE-small benchmark exists but uses an intentionally lexical dataset.
- Docker/Podman/qdrant-client unavailable; git has no remote configured.

| Current concept | Phase 2 action | Evidence target |
|---|---|---|
| `evals/golden_dataset.json` | preserve lexical baseline | existing RAG evidence |
| `scripts/embedding_benchmark.py` | add adversarial dataset mode | `evidence/benchmarks/adversarial-embedding-comparison.json` |
| `scripts/chaos_load.py` | add concurrency sweep | `evidence/benchmarks/load-curve.json` |
| `README.md` | add demo/readiness/benchmark interpretation | reproducible commands |
| Git remote / Actions | inspect only until authorized and configured | explicit blocker |
| Docker/Qdrant/OTLP backend | inspect only until runtime exists | explicit blocker |

Phase 2 preserves the original benchmark and generated caches remain ignored.
Rollback is a `git revert` of the Phase 2 commit; no destructive external action
is authorized without an explicit remote/credential decision.
