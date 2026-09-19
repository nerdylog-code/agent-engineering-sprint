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
