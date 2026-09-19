# Architecture Draft — Agent Engineering Sprint

**Status:** implemented contract draft
**Scope:** architecture and interfaces only; no production-code change is introduced by this document.
**Source of truth:** `CONTEXT_MANIFEST.md`, `docs/architecture.md`, current source contracts.

## 1. System boundary

The project is an offline-first evidence lab, not a hosted agent platform. It has
three explicit boundaries:

```text
request -> deterministic router -> allowlisted tool boundary -> schema validation
                                             |                         |
                                             v                         v
                                         JSONL trace             approval gate

corpus -> parser/chunker -> vector + lexical retrieval -> RRF -> reranker -> cited answer
```

The baseline does not call an external LLM, cloud provider, MCP network server,
or paid API. This makes the baseline suitable for repeatable CI and establishes
a control experiment before optional provider adapters are introduced.

## 2. Module contracts

### `src/agent_lab/models.py`

- `AgentRequest`: non-empty `objective` and `user_input`, request ID, metadata.
- `RouteDecision`: route, optional selected tool, human-readable reason.
- `StructuredOutput`: answer, route, selected tool, confidence in `[0, 1]`,
  approval flag and citations. `validate()` rejects wrong types and empty values.
- `ToolResult`: success, output/error and blocked flag.
- `TraceEvent`: the stable observability row.
- `AgentRunResult`: terminal status, route, tool result, retries, latency and
  optional structured response.

### `src/agent_lab/router.py`

`route_request(objective, user_input) -> RouteDecision` is deterministic. It
returns one of `general_agent`, `tool_agent`, or `rag_agent`. Arithmetic/tool
signals select `calculator` or `lookup_faq`; retrieval/citation signals select
`rag_agent`. The reason is recorded so routing accuracy can be evaluated without
an LLM judge.

### `src/agent_lab/tools.py`

`ToolRegistry` is the MCP-style local boundary:

1. only registered names can execute;
2. tool names follow a safe identifier grammar;
3. dunder argument keys are rejected;
4. handlers are responsible for read-only local behavior;
5. tool output containing known instruction-substitution markers is blocked;
6. operational failures become `ToolResult(ok=False)` rather than escaping the
   orchestrator.

The calculator walks an AST and permits only numeric literals and bounded
arithmetic operators. It never calls Python `eval()`.

### `src/agent_lab/orchestrator.py`

The orchestrator owns the lifecycle:

1. create `TraceCollector`;
2. route the request;
3. invoke the selected allowlisted tool, if any;
4. generate a deterministic candidate response;
5. validate structured output;
6. retry only within the configured bound (`0..5`);
7. require explicit human approval when requested;
8. emit a terminal result and flush JSONL.

Terminal statuses are `completed`, `awaiting_approval`, `rejected`, and
`failed`. A terminal status is never inferred from a successful function call;
it is returned and traced.

### `src/agent_lab/tracing.py`

The trace schema is stable and append-only JSONL:

```text
trace_id
run_id
agent
model
tool
event
input_tokens
output_tokens
latency
status
retry_count
error
timestamp
metadata
```

Token values are deterministic estimates for the offline baseline. Secret-like
metadata values are redacted before persistence. The trace measures process
behavior; it is not a claim about remote model quality.

## 3. Production RAG contracts

### Ingestion

`Document` preserves ID, title, text and metadata. `chunk_text()` creates
bounded overlapping `Chunk` values without losing `document_id`; this allows
citations to point back to the source document.

### Retrieval

`HybridRetriever.search()` supports:

- `vector`: hashed local embedding cosine ranking;
- `keyword`: lexical token overlap;
- `hybrid`: Reciprocal Rank Fusion of both rankings;
- `rerank=True`: evidence-aware final ordering.

`answer()` refuses to fabricate an evidence-backed answer when no lexical
context is found. A successful answer carries document IDs as citations and
measures groundedness/relevance over the retrieved context.

### Evaluation

`evaluate_modes()` runs the same 50-question golden dataset over the same 100
document corpus for vector-only, hybrid, and hybrid-plus-reranker variants. It
returns Recall@1/3/5, MRR, groundedness, answer relevance and question count.
No comparison number is hand-written in production code.

## 4. Optional dependencies and adapters

- Runtime core: Python standard library only.
- `pytest` and `ruff`: development extras used by CI.
- FastAPI and Pydantic: optional API-contract extras, not required for the core.
- Real embedding provider, cross-encoder, MCP SDK and LLM provider: future
  adapters must preserve the local interfaces and report provider/model/cost
  metadata explicitly.

An adapter may not silently turn the deterministic evidence into a remote claim.
Provider experiments need a separate evidence directory and environment label.

## 5. Operational contracts

- CI gate order: compile → lint → tests → evals → security → RAG smoke.
- Docker workflow builds and smoke-tests; it does not push an image.
- GitHub Actions is prepared but requires a remote repository to execute.
- External credentials and course completion remain human-owned.
- The Context Manifest and evidence files are part of the release record.

## 6. Files NOT touched by this draft author

This document is architecture-only. The following production or contract files
are explicitly outside the draft author’s write scope:

| Path | Reason |
|---|---|
| `src/` | production implementation owned by the main orchestrator |
| `tests/` | regression suite owned by the QA implementation pass |
| `evals/` | executable evaluation suite owned by the QA implementation pass |
| `.github/` | CI workflow owned by the delivery implementation pass |
| `README.md` | public project documentation owned by the delivery pass |
| `pyproject.toml` | packaging contract owned by the delivery pass |

## 7. Open evolution points

1. Add an OpenTelemetry exporter behind `TraceCollector`.
2. Add a real MCP transport adapter with per-tool permissions and auth.
3. Add FastAPI endpoints without coupling HTTP to retrieval internals.
4. Run provider comparisons only with fresh, independently labeled evidence.
5. Add adversarial injection datasets beyond the current marker-based baseline.
