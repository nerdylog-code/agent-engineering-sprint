# Adaptive Decision Routing

## Scope

This phase evaluates four strategies inside `agent-engineering-sprint`:

```text
Rules → Laya → LLM → Hybrid
```

The existing `agent_lab.router.route_request()` is the deterministic baseline
and is intentionally unchanged. `src/agent_lab/decision/rules_router.py` wraps
it; the new routers are siblings, not replacements.

The earlier `experiments/laya-decision-engine` remains an isolated POC. This
repository keeps a small local contract because the public sprint must clone and
run without a sibling checkout or Laya weights. The two contracts share the same
semantics but are not coupled through a fragile local path dependency.

## Contract and probability provenance

`RouteDecisionResult` distinguishes:

- `probability`: a probability that can be evaluated when the provider exposes a
  valid distribution (`selected_probability` for Laya choice);
- `entropy_confidence`: Laya's normalized entropy confidence;
- `self_reported_confidence`: an LLM's structured field, never treated as a
  calibrated probability;
- `probabilities`: the full distribution when available;
- `probability_source` and `calibration_status`.

Rules have no probability. LLMs have no probability unless a separate calibrated
model is supplied. Laya's domain calibration is not assumed by this benchmark.

## Exact upstream semantics

For raw logits `l` and the selected temperature `T`, upstream computes
`p_i = softmax(l_i / T)`. Temperature is selected by question type and option
bucket; the observed checkpoint warning clamps `choice:11+` from `0.1006` to
`0.5`, so those buckets are marked `uncalibrated_high_cardinality`.

- **`choice`**: the selected class is `argmax(p)`. `probability` is the selected
  class's `p_i`. Upstream `confidence` is instead
  `1 - H(p)/log(k)`, where `H(p) = -sum(p_i log(p_i))`. It measures concentration,
  not the selected-class posterior.
- **`score`**: `score = sum(i * p_i)` is an expected ordinal value. Its upstream
  `confidence` is the same entropy-concentration score over levels; it is not a
  scalar probability. Calibration must use the level distribution (multiclass
  Brier, ordinal/RPS, or per-level ECE).
- **`noul`**: `noul` is the true-class probability `p_true` for the binary head,
  while upstream `confidence = max(p_true, 1 - p_true)`. A binary Brier score
  uses `p_true`, not certainty in the selected class.

This router evaluates only `choice`, so Brier/ECE use the complete choice
vector and selected probability. It never aliases entropy confidence or an LLM
self-report into a calibrated probability.

## Strategies

### RulesRouter

Uses the existing deterministic function and marks its output as
`probability_source=deterministic_rule`. High-signal arithmetic and explicit
retrieval requests are considered obvious by HybridRouter. Authorization,
tool allowlists, approval and safety gates remain deterministic.

### LayaRouter

Uses the optional upstream `laya.Router` and one typed `choice` question over
`general_agent`, `tool_agent` and `rag_agent`. Missing dependency, missing
checkpoint, CUDA failure and malformed output become explicit errors; no mock is
silently substituted. PT-BR/mixed requests can select the multilingual
checkpoint when the language field is known.

### LLMRouter

Uses an injected structured-output provider. `OllamaJSONProvider` is available
for a local Ollama model, with JSON schema constraints and deterministic
temperature `0`. Its confidence is recorded as `self_reported_confidence` and
excluded from Brier/ECE.

### HybridRouter

1. Empty input → abstain.
2. Obvious deterministic rule → Rules.
3. Laya selected probability over the configurable threshold and no high-cardinality calibration warning → Laya.
4. Otherwise → LLM.
5. If Laya and LLM fail → explicit Rules fallback or abstain.

No route result grants permission to execute a tool or a critical action.

## Evaluation splits

`evals/router_dataset/` is separate from the RAG corpora:

- `development`: 120 cases; rule/dataset iteration only.
- `calibration`: 60 cases; threshold exploration only.
- `held_out_test`: 60 cases; final evaluation, never used to select a threshold.

Each split is balanced across three routes and four difficulty bands, with
English, PT-BR, mixed language, typos/distractors, injection strings, empty
input, long input and two-intention cases.

Threshold selection is calibration-only: grid `[0.50, 0.60, 0.70, 0.75, 0.80,
0.85, 0.90, 0.95]`, retain accuracy within 0.05 of the grid maximum, then
choose the lowest ECE under the 0.90 escalation budget. This selected `0.90`
for the held-out Hybrid run; the selection and cache policy are recorded in
`evidence/router-benchmark-calibration.json`.

## Evidence commands

```bash
python scripts/generate_router_dataset.py
python -m pytest -q

# Rules-only baseline
python scripts/router_benchmark.py --split held_out_test --strategies rules

# Real Laya using the isolated POC environment
HF_HUB_OFFLINE=1 <laya-poc-venv>/Scripts/python.exe scripts/router_benchmark.py \
  --split held_out_test --strategies laya --laya-preload --device cuda

# Local Ollama LLM baseline
<laya-poc-venv>/Scripts/python.exe scripts/router_benchmark.py \
  --split held_out_test --strategies llm --llm-provider ollama --llm-model qwen2.5:7b

# Hybrid, with calibration sweep on calibration split
<laya-poc-venv>/Scripts/python.exe scripts/router_benchmark.py \
  --split calibration --strategies hybrid --laya-preload --device cuda \
  --llm-provider ollama --llm-model qwen2.5:7b
```

Generated evidence is stored under `evidence/` and traces contain metadata only,
not request content.

## Security boundary

Adaptive routing is operational guidance. It cannot replace:

- tool allowlists;
- JWT/RBAC and tenant ACL;
- prompt-injection and PII gates;
- structured-output validation;
- rate limits, approval or MCP permissions.

## Decision rule

The benchmark is allowed to conclude that Rules are better. A Hybrid default is
not approved merely because it combines more components; it must improve the
held-out quality/latency/fallback trade-off without unsafe automatic routing.
