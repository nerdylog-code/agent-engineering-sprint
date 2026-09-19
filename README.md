# Agent Engineering Sprint

![Local CI](https://img.shields.io/badge/Local%20CI-PASS-2ea44f)
![Security](https://img.shields.io/badge/Security-0%20findings-2ea44f)
![Runtime](https://img.shields.io/badge/Runtime-offline--first-1f6feb)

Projeto isolado e reproduzível para transformar o sprint de Agents, CI/CD,
evals, observabilidade, MCP e RAG em **prova técnica executável**. O runtime
default não depende de API paga, credencial, cloud ou modelo remoto.

> **Regra de evidência:** os números abaixo vêm de execução local registrada em
> `evidence/`. Nenhuma credencial externa é marcada como concluída sem prova da
> conta do usuário.

## Estado verificado

Última execução local do pacote:

| Gate | Resultado observado |
|---|---:|
| Compilação `compileall` | PASS |
| Testes de `tests/` | 43 passed |
| Evals de `evals/` | 7 passed |
| Pytest total | 50 passed, 3 subtests |
| Branch coverage | 81.66% |
| Mypy | PASS |
| Bandit | PASS |
| Dependency audit | PASS, 0 known vulnerabilities in project runtime |
| Security scan | 45 arquivos, 0 findings |
| Agent task success | 1.0 (8/8 runs) |
| Tool selection accuracy | 1.0 |
| Structured-output validity | 1.0 |
| RAG corpus | 100 documentos, 100 chunks |
| RAG golden set | 50 perguntas |
| Adversarial RAG set | 54 perguntas, 48 answerable + 6 abstention |
| Hybrid + reranker Recall@1 | 1.0 |
| Hybrid + reranker MRR | 1.0 |
| MiniCPM5 real tool loop | PASS, 2 turns / 12.257931s |
| Local benchmark | 100 runs, agent/RAG p50/p95 recorded |
| FastEmbed benchmark | PASS, BGE small vs hashing measured |
| Adversarial embedding benchmark | FastEmbed Recall@1 0.770833 vs hashing 0.583333 |
| OpenTelemetry | SDK in-memory spans for HTTP/agent/provider/tool/RAG |
| MCP HTTPS | PASS, self-signed TLS + JWT tool scope allow/deny |
| Chaos/load | 100/100 requests; timeout/429/500/malformed/lock recovery |
| Load curve | concurrency 1→200; P95 10.3327→677.4062 ms |

Os artefatos completos ficam em:

- `evidence/latest.json`
- `evidence/metrics/agent_metrics.json`
- `evidence/eval-results/rag_metrics.json`
- `evidence/traces/agent-matrix.jsonl`
- `evidence/traces/minicpm5-tool-call.jsonl`
- `evidence/provider/minicpm5-tool-call.json`
- `evidence/provider/mcp-stdio-protocol.json`
- `evidence/benchmarks/local-baseline.json`
- `evidence/benchmarks/embedding-comparison.json`
- `evidence/benchmarks/adversarial-embedding-comparison.json`
- `evidence/benchmarks/load-curve.json`
- `evidence/benchmarks/chaos-load.json`
- `evidence/security/mcp-http-tls.json`
- `evidence/security-tests.md`
- `evidence/traces/otel-spans-demo.json`
- `evidence/demo/five-minute-demo.json`
- `evals/golden_dataset.json`
- `evals/adversarial_dataset.json`

## Production Readiness

### Implemented and locally verified

✓ JWT authentication with claims, RBAC and tenant isolation

✓ Persistent RAG and real FastEmbed benchmark against hashing

✓ Adversarial retrieval benchmark with semantic gain and explicit abstention

✓ Agent/tool execution and structured outputs

✓ MCP stdio plus local MCP HTTP/TLS, JWT scopes, timeout and audit decisions

✓ Rate limiting, retries, circuit breaker and failure handling

✓ OpenTelemetry SDK spans for HTTP, router, agent, provider, retrieval and tools

✓ Async load/chaos harness, static security analysis and automated tests

✓ Load curve at concurrency 1, 10, 25, 50, 100 and 200

### Prepared but not externally verified

△ Docker image and compose deployment

△ GitHub Actions hosted execution and branch protection

△ Qdrant/vector database deployment

△ Managed secrets and centralized observability export

△ Cloud deployment, rollback and distributed load testing

### Requires external infrastructure or human approval

○ Production identity provider and key rotation

○ Managed vector database with production ACL policy

○ Centralized telemetry backend, SLOs and retention

○ Azure/AWS production account and budget

○ Formal SOC 2/LGPD review and release approval

## Five-minute demo

The complete local demo is reproducible without Docker, cloud credentials or a
remote model:

```bash
cd D:/Hermes/ErisWorkspace/agent-engineering-sprint
PYTHONPATH=src python scripts/five_minute_demo.py
PYTHONPATH=src python scripts/adversarial_embedding_benchmark.py
PYTHONPATH=src python scripts/load_curve.py
```

What the demo proves:

1. Agent and RAG requests complete with citations.
2. Tenant A attempting tenant B returns `403`.
3. A normal user attempting the admin route returns `403`; an admin returns `200`.
4. An MCP calculator call with scope returns `200`; without scope returns `403`.
5. The in-memory OpenTelemetry span names are emitted.
6. The adversarial benchmark shows measured semantic retrieval separation.
7. The load curve makes P95 degradation visible from concurrency 1 to 200.

The demo is a local ASGI/TestClient proof, not a hosted public deployment.

## O que foi implementado

### Agent Lab (`src/agent_lab`)

- Router determinístico para `general_agent`, `tool_agent` e `rag_agent`.
- Tools allowlisted: `calculator` seguro via AST e `lookup_faq` somente leitura.
- Structured output validado por contrato, com retries limitados a 5.
- Human-in-the-loop explícito: `awaiting_approval`, `completed` ou `rejected`.
- Proteção contra saída de tool com marcadores de prompt injection.
- Traces JSONL com `trace_id`, `run_id`, `agent`, `model`, `tool`, tokens,
  latência, status, retry count e erro.
- Provider OpenAI-compatible real com timeout, retry, circuit breaker, parsing
  de tool calls e loop provider → tool → provider.
- Safety gate para prompt injection/PII e schemas de tools com propriedades
  adicionais bloqueadas.
- ACL por `tenant_id` e `principal` no retrieval, sem permitir cross-tenant
  citations.
- FastAPI com health/readiness, request IDs, métricas Prometheus básicas e
  JWT HS256 opcional com claims tenant/principal para rotas `/v1/*`.
- Rate limit por janela fixa com resposta `429` e `Retry-After`.
- Servidor stdio JSON-RPC com `initialize`, `tools/list` e `tools/call`, além
  de teste de subprocesso real sobre a registry allowlisted.

### Production RAG (`src/production_rag`)

- Corpus sintético determinístico de 100 documentos.
- Chunking com overlap.
- Embeddings locais por hashing, sem download de modelo.
- Busca vector-only, keyword-only e hybrid com Reciprocal Rank Fusion.
- Backend de embeddings substituível: hashing control e FastEmbed ONNX real.
- Reranker lexical/semântico com bônus de evidência exata.
- Respostas com citações, groundedness e answer relevance.
- Comparação mensurada entre vector-only, hybrid e hybrid + reranker.

### CI/CD e distribuição

- `.github/workflows/ci.yml`: compile, Ruff, testes, evals, security gate,
  mypy, Bandit, cobertura, pip-audit, geração de evidências e CI estrito.
- `.github/workflows/docker.yml`: build e smoke test do container.
- `Dockerfile` e `docker-compose.yml`.
- `scripts/ci.py`: contrato local equivalente ao pipeline.
- `scripts/security_scan.py`: secrets, private keys e shell escape patterns.
- `scripts/minicpm5_tool_call_probe.py`: prova real do loop de tool calling local.
- `scripts/benchmark.py`: baseline reproduzível de throughput e p50/p95.
- `scripts/embedding_benchmark.py`: comparação hashing vs FastEmbed com Recall/MRR.
- `scripts/adversarial_embedding_benchmark.py`: benchmark semântico separado do baseline lexical.
- `scripts/mcp_https_demo.py`: HTTPS local real com JWT e scope de tool.
- `scripts/chaos_load.py`: carga assíncrona e injeção de falhas com evidência JSON.
- `scripts/load_curve.py`: curva local de concorrência 1→200.
- `scripts/otel_trace_demo.py`: inventário de spans redigido para demonstração.
- `scripts/five_minute_demo.py`: fluxo compacto de RAG, JWT, RBAC, MCP e OTel.

## Quickstart

Windows PowerShell e Git Bash podem usar o mesmo comando com `PYTHONPATH`:

```bash
cd D:/Hermes/ErisWorkspace/agent-engineering-sprint
PYTHONPATH=src python -m agent_lab.cli demo --json
PYTHONPATH=src python -m production_rag.cli evaluate --json
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m unittest discover -s evals -v
PYTHONPATH=src python scripts/ci.py --strict
PYTHONPATH=src python scripts/generate_evidence.py
```

O núcleo determinístico não exige dependências de provider. Os extras `api`,
`dev`, `security` e `observability` são instalados pelos gates para validar
FastAPI, cobertura, mypy, Bandit, pip-audit e OpenTelemetry. `embeddings` é
opcional porque baixa o modelo FastEmbed local.

## Contrato de execução

```text
Agent request
     |
     v
  Router -----> bounded retry ---> structured output
     |                                  |
     v                                  v
  Tool registry ----> approval ----> final response
     |
     v
   JSONL trace
```

```text
Documents -> parser -> chunks -> vector + keyword -> RRF -> reranker
                                                        |
                                                        v
                                              answer + citations + evals
```

Leia `docs/architecture.md`, `docs/QA_SECURITY_PLAN.md` e
`docs/ENTERPRISE_READINESS.md` para os contratos
mais detalhados.

## Docker

Se o daemon Docker estiver disponível:

```bash
docker build -t agent-engineering-sprint:local .
docker run --rm agent-engineering-sprint:local
# ou
 docker compose run --rm agent-lab
```

A verificação do daemon é uma condição do ambiente; o workflow GitHub continua
sendo fornecido mesmo quando o host local não possui Docker Desktop.

## Credenciais externas

`docs/credential-checklist.md` separa o que o agente pode preparar do que exige
login e avaliação da pessoa: Microsoft Applied Skills, cursos externos,
Hugging Face e AWS. Este repositório **não afirma** que qualquer uma delas foi
concluída.

## Estrutura

```text
src/agent_lab/          API, provider, tools, safety, traces, storage
src/production_rag/     ingestão, retrieval, ACL, reranker, SQLite, métricas
tests/                  testes de comportamento
 evals/                 golden dataset + eval suite
scripts/                CI local, security scan, evidence generator
docs/                   arquitetura, ADRs, entrevista, conhecimento
evidence/               resultados medidos e traces
.github/workflows/      ci.yml e docker.yml
```

## Limites deliberados

- O baseline default é determinístico, mas o loop real MiniCPM5 foi validado e
  está separado em evidência própria; isso não generaliza para todos os modelos.
- O embedding por hashing é baseline reproduzível, não substituto de um modelo
  de embedding de produção.
- FastEmbed BGE small foi executado localmente; neste dataset lexical ambos
  tiveram Recall/MRR 1.0, portanto nenhum vencedor é declarado sem dataset
  semanticamente ambíguo.
- O timeout de tool limita o chamador, mas não mata thread Python já iniciada;
  tool não confiável ainda exige processo/container isolado em produção.
- Não há GitHub Actions hospedado executado porque este diretório não possui
  remote GitHub configurado; o workflow está pronto para um push futuro.
- Não há certificado ou badge externo inventado.
- MCP protocol completo com client/server remoto e isolamento continua pendente;
  o subconjunto stdio e o boundary HTTPS/JWT local já foram validados.
