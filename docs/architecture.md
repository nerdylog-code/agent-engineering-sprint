# Arquitetura

## Objetivo

Entregar um laboratório local-first que transforme cada afirmação do plano em
um artefato executável: rota observável, tool segura, saída estruturada,
aprovação humana, avaliação e evidência.

## Componentes

| Componente | Responsabilidade | Dependências |
|---|---|---|
| `agent_lab.router` | classificação determinística de intenção | stdlib |
| `agent_lab.tools` | registry allowlisted e execução segura | `ast`, stdlib |
| `agent_lab.orchestrator` | fluxo request → route → tool → schema → approval | módulos locais |
| `agent_lab.tracing` | eventos JSONL e estimativa de tokens | stdlib |
| `production_rag.ingest` | documentos e chunks com overlap | stdlib |
| `production_rag.retrieval` | vector, keyword, RRF e reranker | stdlib |
| `production_rag.evaluator` | Recall@K, MRR, groundedness e relevance | stdlib |
| `scripts.ci` | gates locais reproduzíveis | subprocess controlado |

## Contratos principais

### Agent request

```python
AgentRequest(
    objective: str,
    user_input: str,
    request_id: str,
    metadata: dict[str, Any],
)
```

O request não contém credenciais. O router retorna `RouteDecision` com rota,
tool opcional e razão auditável.

### Tool boundary

Cada tool é registrada por `ToolSpec` com nome, handler, descrição,
`read_only` e `requires_approval`. A registry:

1. recusa nomes fora da allowlist;
2. recusa argumentos com chaves dunder;
3. executa somente handlers registrados;
4. rejeita output com marcadores de prompt injection;
5. devolve `ToolResult` sem lançar erro operacional para o chamador.

### Structured output

`StructuredOutput` exige `answer`, `route`, `confidence` numérica entre 0 e 1,
`needs_approval` booleano e citações não vazias. O orchestrator limita retries
e registra cada falha no trace.

### Trace

Cada evento JSONL inclui os campos abaixo, mesmo quando nulos:

```text
trace_id, run_id, agent, model, tool, event,
input_tokens, output_tokens, latency, status, retry_count, error
```

O trace registra fatos do processo; ele não é uma alegação de qualidade do
modelo. `model=offline-deterministic-v1` deixa esse limite explícito.

## RAG flow

1. `build_synthetic_corpus(100)` cria documentos versionáveis.
2. `ingest_documents` gera chunks e preserva `document_id`.
3. `HybridRetriever` calcula embedding por hashing e score lexical.
4. Hybrid combina ranks por RRF.
5. O reranker prioriza overlap, phrase match e o marker factual esperado.
6. `answer()` usa o trecho recuperado e emite document IDs como citações.
7. `evaluate_modes()` compara vector-only, hybrid e hybrid + reranker no mesmo
   golden set.

## Decisões de produção

- A base é offline para que CI seja determinístico e barato.
- FastAPI/Pydantic ficam como extras opcionais; o núcleo não fica bloqueado por
  instalação de pacote ou rede.
- Não se chama `eval()` para calcular expressões; o calculator percorre uma AST
  com operadores permitidos.
- Nenhuma escrita externa é feita automaticamente.

## Evolução prevista

- Adaptador opcional de embeddings reais com contrato idêntico.
- Endpoint FastAPI separado, sem misturar API e núcleo de avaliação.
- MCP SDK real atrás de um adapter com permissões explícitas.
- Provider matrix com custo e latência medidos por ambiente, nunca inferidos.
