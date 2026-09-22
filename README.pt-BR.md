# Agent Engineering Sprint

[English](README.md) | **Português**

[![CI](https://github.com/nerdylog-code/agent-engineering-sprint/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/nerdylog-code/agent-engineering-sprint/actions/workflows/ci.yml)
[![Docker](https://github.com/nerdylog-code/agent-engineering-sprint/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/nerdylog-code/agent-engineering-sprint/actions/workflows/docker.yml)
[![License](https://img.shields.io/github/license/nerdylog-code/agent-engineering-sprint)](LICENSE)

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

✓ Docker build e smoke test hospedados — [execução 35681408654](https://github.com/nerdylog-code/agent-engineering-sprint/actions/runs/35681408654)

✓ GitHub Actions CI hospedado — [execução 35681408760](https://github.com/nerdylog-code/agent-engineering-sprint/actions/runs/35681408760)

△ Docker Compose fora do smoke test hospedado; validar localmente quando o daemon estiver disponível

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

## Roteamento adaptativo e evidência de decisão

A fase adiciona `src/agent_lab/decision/` sem alterar o contrato de
`agent_lab.router.route_request()`. O dataset independente tem 240 casos:
`development` 120, `calibration` 60 e `held_out_test` 60, balanceados entre
`general_agent`, `tool_agent` e `rag_agent`, com PT-BR, mixed, ambiguidade,
prompt injection, input vazio e 30k caracteres.

No held-out final (60 casos; números gerados em
`evidence/router-benchmark-heldout-final.json`):

| Estratégia | Accuracy | Macro-F1 | p50 / p95 ms | Brier / ECE |
|---|---:|---:|---:|---:|
| Rules | 0.3667 | 0.2713 | 0.003 / 0.018 | n/a / n/a |
| Laya CUDA | **0.7500** | **0.7436** | 19.685 / 42.843 | 0.2962 / 0.0676 |
| LLM local `qwen2.5:7b` | 0.7167 | 0.7194 | 540.750 / 940.697 | n/a / n/a |
| Hybrid, threshold 0.90 | 0.5500 | 0.5263 | 9.316 / 2063.055 | 0.0021 / 0.0269 |

Esses números valem somente para este corpus sintético. O Hybrid fez 22 chamadas
LLM contra 60 do baseline LLM (38 a menos; redução de 63,33%). O provider foi
local e os custos foram configurados como zero, então a evidência registra
economia estimada de `0.0` USD; nenhuma economia em cloud é reivindicada. O
Brier/ECE do Hybrid usa apenas sete vetores Laya aceitos e, portanto, é
seleção-biased; a confiança autodeclarada do LLM não é probabilidade calibrada.
No mesmo artefato, PT-BR (n=24 por estratégia) mede Rules 0.2917, Laya
multilingual 0.7083, LLM local 0.7917 e Hybrid 0.5417; isso é medição, não
garantia multilíngue.
A semântica detalhada de `probability`, `entropy_confidence`, `score`, `noul` e
`temperature` está em `docs/ADAPTIVE_DECISION_ROUTING.md`. A varredura de
thresholds usa somente `calibration`; a política registrada selecionou 0.90
antes do held-out.

Os probes de cardinalidade 2/3/4/5/8/10/11/12/16 estão em
`evidence/router-high-cardinality.json`. O warning real do checkpoint informa
que `choice:11+` foi clampado de `0.1006` para `0.5`; esses buckets ficam
marcados como não calibrados e não passam pelo gate automático do Hybrid.
Traces redigidos ficam em `evidence/traces/`, e a análise de erros em
`docs/ROUTING_ERROR_ANALYSIS.md`.

Laya/Ollama são runtimes opcionais. Sem eles, execute os testes determinísticos
e o benchmark Rules; não atribua evidência Laya/LLM a um clone que não os
executou.

## Safety + abstention sprint

O baseline anterior permanece congelado como `current safety gate = FAILED`
porque `false_auto_accept = 2/5 = 0,40`. Foi criado um dataset independente
`evals/router_safety_dataset/` com 180 casos e 133 abstentions esperadas.

No held-out de segurança, a melhor política medida foi **Laya com abstention
explícito + safety pre-gate determinístico**:

| Política | Coverage | Selective accuracy | Unsafe auto-route | False auto-accept |
|---|---:|---:|---:|---:|
| Laya threshold + safety | 0,1333 | 0,6667 | 0,0444 | 1 |
| **Laya explícito + safety** | **0,1778** | **0,8750** | **0,0222** | **0** |
| LLM + safety | 0,4000 | 0,5000 | 0,2000 | 6 |
| Hybrid + safety | 0,4000 | 0,4444 | 0,2222 | 6 |

Isso é resultado de selective routing, não autorização para automação sensível.
Routing é separado de authorization determinística: refund, exclusão, alteração
fiscal, escrita externa, envio de email e credenciais continuam exigindo policy e
aprovação. Detalhes em `docs/ROUTING_SAFETY_ANALYSIS.md` e nos artefatos
`evidence/router-safety-benchmark.json` e `evidence/router-selective-risk.json`.

Modo recomendado:

```text
safety pre-gate → Laya abstention explícito → authorization → aprovação humana
```

Não iniciar automação fiscal sensível antes de aceitar explicitamente o trade-off
entre coverage e risco.

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
- O CI principal já possui execução hospedada com sucesso: [run 35593625355](https://github.com/nerdylog-code/agent-engineering-sprint/actions/runs/35593625355). O badge acima é ligado ao workflow real.
- O workflow Docker inicia o container em background, consulta `/healthz` com limite, imprime logs em falhas e faz cleanup. A execução hospedada pós-correção passou: [run 35681408654](https://github.com/nerdylog-code/agent-engineering-sprint/actions/runs/35681408654).
- MCP protocol completo com client/server remoto e isolamento continua pendente;
  o subconjunto stdio e o boundary HTTPS/JWT local já foram validados.
