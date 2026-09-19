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
| Testes de `tests/` | 29 passed |
| Evals de `evals/` | 7 passed |
| Pytest total | 36 passed, 3 subtests |
| Branch coverage | 81.14% |
| Mypy | PASS |
| Bandit | PASS |
| Dependency audit | PASS, 0 known vulnerabilities in project runtime |
| Security scan | 36 arquivos, 0 findings |
| Agent task success | 1.0 (8/8 runs) |
| Tool selection accuracy | 1.0 |
| Structured-output validity | 1.0 |
| RAG corpus | 100 documentos, 100 chunks |
| RAG golden set | 50 perguntas |
| Hybrid + reranker Recall@1 | 1.0 |
| Hybrid + reranker MRR | 1.0 |
| MiniCPM5 real tool loop | PASS, 2 turns / 12.257931s |
| Local benchmark | 100 runs, agent/RAG p50/p95 recorded |

Os artefatos completos ficam em:

- `evidence/latest.json`
- `evidence/metrics/agent_metrics.json`
- `evidence/eval-results/rag_metrics.json`
- `evidence/traces/agent-matrix.jsonl`
- `evidence/traces/minicpm5-tool-call.jsonl`
- `evidence/provider/minicpm5-tool-call.json`
- `evidence/provider/mcp-stdio-protocol.json`
- `evidence/benchmarks/local-baseline.json`
- `evals/golden_dataset.json`

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
  Bearer token opcional para rotas `/v1/*`.
- Rate limit por janela fixa com resposta `429` e `Retry-After`.
- Servidor stdio JSON-RPC com `initialize`, `tools/list` e `tools/call`, além
  de teste de subprocesso real sobre a registry allowlisted.

### Production RAG (`src/production_rag`)

- Corpus sintético determinístico de 100 documentos.
- Chunking com overlap.
- Embeddings locais por hashing, sem download de modelo.
- Busca vector-only, keyword-only e hybrid com Reciprocal Rank Fusion.
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
`dev` e `security` são instalados pelos gates para validar FastAPI, cobertura,
mypy, Bandit e pip-audit.

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
- Não há GitHub Actions hospedado executado porque este diretório não possui
  remote GitHub configurado; o workflow está pronto para um push futuro.
- Não há certificado ou badge externo inventado.
- MCP protocol completo com autenticação, client/server remoto e isolamento
  continua pendente; o subconjunto stdio local já foi validado com subprocesso.
