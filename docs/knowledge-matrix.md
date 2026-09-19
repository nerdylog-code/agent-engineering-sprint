# Knowledge matrix

| Tema | Sei demonstrar no código | Evidência | Próximo passo humano |
|---|---|---|---|
| Router | sim, 3 rotas e razões | `evals/test_router.py` | explicar trade-offs |
| Tools | sim, calculator/FAQ allowlist | `tests/test_agent_lab.py` | adaptar para MCP real |
| Structured output | sim, schema + retry | `evals/test_structured_output.py` | validar contrato com provider |
| Human approval | sim, pending/approved/rejected | `test_human_approval_is_explicit` | desenhar UX |
| Tracing / OpenTelemetry | GREEN: JSONL + SDK spans HTTP/router/agent/provider/RAG/tool | `tests/test_telemetry.py`, `evidence/` | exportar para backend central |
| Evals | sim, deterministic + metrics | `evals/` | adicionar LLM-as-a-Judge opcional |
| RAG ingest | sim, 100 docs + chunks | `evidence/eval-results/rag_metrics.json` | testar PDFs reais |
| Hybrid retrieval / embeddings | GREEN: vector + keyword + RRF + FastEmbed medido | `docs/embedding-benchmark.md` | dataset semântico difícil |
| Adversarial retrieval | GREEN: 54 cases, FastEmbed gain + abstention measured | `docs/adversarial-embedding-benchmark.md` | expand multilingual model/dataset |
| Reranking | sim, score lexical/semântico | RAG metrics | comparar cross-encoder real |
| MCP stdio + HTTP/TLS | GREEN local: scopes, timeout e audit; remoto ainda YELLOW | `evidence/security/mcp-http-tls.json` | isolar worker e conectar identidade externa |
| JWT/RBAC/multi-tenancy | GREEN local: claims, exp/aud/iss, role e cross-tenant tests | `evidence/security-tests.md` | RS256/issuer/KMS externo |
| Load/chaos | GREEN local: 100 concorrentes + falhas/recovery | `docs/chaos-load.md` | carga distribuída |
| Load curve | GREEN local: 1→200 concorrência e P95 degradation | `docs/load-curve.md` | repeat on Docker/network |
| CI/CD | workflows e CI local | `.github/workflows/` | conectar remote e observar Actions |
| Docker | Dockerfile + workflow | `Dockerfile` | executar se daemon disponível |
| Microsoft credential | não comprovada | `docs/credential-checklist.md` | login + assessment humano |
| Hugging Face credential | não comprovada | `docs/credential-checklist.md` | login + quiz ≥80% |
| AWS microcredential | não comprovada | `docs/credential-checklist.md` | hands-on no ambiente AWS |
