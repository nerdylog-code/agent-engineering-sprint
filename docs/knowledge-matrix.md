# Knowledge matrix

| Tema | Sei demonstrar no código | Evidência | Próximo passo humano |
|---|---|---|---|
| Router | sim, 3 rotas e razões | `evals/test_router.py` | explicar trade-offs |
| Tools | sim, calculator/FAQ allowlist | `tests/test_agent_lab.py` | adaptar para MCP real |
| Structured output | sim, schema + retry | `evals/test_structured_output.py` | validar contrato com provider |
| Human approval | sim, pending/approved/rejected | `test_human_approval_is_explicit` | desenhar UX |
| Tracing | sim, JSONL com campos obrigatórios | `evidence/traces/agent-matrix.jsonl` | exportar OTEL |
| Evals | sim, deterministic + metrics | `evals/` | adicionar LLM-as-a-Judge opcional |
| RAG ingest | sim, 100 docs + chunks | `evidence/eval-results/rag_metrics.json` | testar PDFs reais |
| Hybrid retrieval | sim, vector + keyword + RRF | `production_rag/retrieval.py` | trocar embedding por provider medido |
| Reranking | sim, score lexical/semântico | RAG metrics | comparar cross-encoder real |
| MCP | boundary conceitual segura | `docs/SECURITY.md` | completar Applied Skill manualmente |
| CI/CD | workflows e CI local | `.github/workflows/` | conectar remote e observar Actions |
| Docker | Dockerfile + workflow | `Dockerfile` | executar se daemon disponível |
| Microsoft credential | não comprovada | `docs/credential-checklist.md` | login + assessment humano |
| Hugging Face credential | não comprovada | `docs/credential-checklist.md` | login + quiz ≥80% |
| AWS microcredential | não comprovada | `docs/credential-checklist.md` | hands-on no ambiente AWS |
