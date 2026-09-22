# Routing Safety, Abstention and Selective Prediction

## Status

The previous Adaptive Decision Routing baseline remains frozen:

```text
Rules: 0.3667 accuracy
Laya: 0.7500 accuracy / 0.7436 Macro-F1
LLM qwen2.5:7b: 0.7167 accuracy / 0.7194 Macro-F1
Hybrid: 0.5500 accuracy / 0.5263 Macro-F1
```

Its original safety gate was **FAILED** because
`false_auto_accept = 2 / 5 = 0.40` on the five abstention cases.
This safety sprint does not reinterpret or overwrite that baseline.

## Independent safety dataset

`evals/router_safety_dataset/` is independent from
`evals/router_dataset/` and contains 180 cases:

| Split | Cases | Expected abstain |
|---|---:|---:|
| development | 90 | 66 |
| calibration | 45 | 34 |
| held_out_test | 45 | 33 |

It contains 19 safety categories, including prompt injection, unsafe actions,
missing context, conflicting intents, malformed/truncated requests, unsupported
language, PT-BR slang, typos, long distractor context, and empty input.

## First-class abstention contract

The router contract keeps routing and abstention separate:

```text
general_agent | tool_agent | rag_agent | ABSTAIN
```

`ABSTAIN` is represented as `RouteDecisionResult(disposition="abstain", route=None)`.
Two strategies are evaluated independently:

1. **Threshold abstention** — route only when selected probability meets the
   threshold; otherwise abstain.
2. **Explicit abstention** — Laya receives an `ABSTAIN` choice describing
   unsafe, ambiguous, or insufficiently determined requests.

The benchmark does not assume the explicit choice is better.

## Held-out safety results

Evidence: `evidence/router-safety-benchmark.json`.
The threshold was selected from calibration at `0.80`: it was the highest-
coverage point on calibration satisfying `unsafe_auto_route_rate <= 0.05`
and `false_auto_accept = 0`.

| Policy | Accuracy | Coverage | Selective accuracy | Unsafe auto-route | False auto-accept |
|---|---:|---:|---:|---:|---:|
| Rules | 0.2444 | 0.9556 | 0.2093 | 0.7556 | 31 |
| Laya threshold + safety gate | 0.8000 | 0.1333 | 0.6667 | 0.0444 | 1 |
| Laya explicit + safety gate | **0.8889** | **0.1778** | **0.8750** | **0.0222** | **0** |
| LLM + safety gate | 0.8000 | 0.4000 | 0.5000 | 0.2000 | 6 |
| Hybrid + safety gate | 0.7778 | 0.4000 | 0.4444 | 0.2222 | 6 |

The explicit Laya policy is the strongest candidate on this safety held-out
set, but its automatic coverage is only 17.78%. It is not permission to
perform sensitive actions. High-risk cases had zero unsafe automatic routes in
the measured run; the remaining unsafe rate came from low-risk semantic
misrouting, including code mixed with natural language.

## Selective risk and calibration

Calibration sweep evidence: `evidence/router-selective-risk.json`.

| Threshold | Coverage | Selective accuracy | Unsafe auto-route | False auto-accept |
|---:|---:|---:|---:|---:|
| 0.50 | 0.2667 | 0.4167 | 0.1556 | 3 |
| 0.70 | 0.2222 | 0.4000 | 0.1333 | 2 |
| 0.80 | 0.1333 | 0.6667 | 0.0444 | 0 |
| 0.90 | 0.1111 | 0.6000 | 0.0444 | 0 |
| 0.95 | 0.0667 | 1.0000 | 0.0000 | 0 |
| 0.98 | 0.0667 | 1.0000 | 0.0000 | 0 |

This shows the safety/coverage trade-off instead of optimizing accuracy alone.
A policy with zero unsafe routes at 6.67% coverage is technically safe but
not yet a useful general router.

## Prompt injection

Evidence: `evidence/router-prompt-injection.json`.

- raw Rules, raw Laya, raw LLM and raw Hybrid remain manipulable on injection
  strings;
- the deterministic safety pre-gate reduced measured route-manipulation to
  zero for the Laya safety-gated policies and the Hybrid safety-gated policy;
- the safety pre-gate is a routing safeguard, not an authorization mechanism.

## Routing versus authorization

`src/agent_lab/decision/authorization.py` makes the boundary explicit:

```text
routing decision != authorization decision
```

Even if a router returns `tool_agent`, deterministic authorization still denies
or requires approval for email sends, refunds, file deletion, fiscal alteration,
external writes, and credential operations.

## PT-BR and multilingual checkpoint

The current safety held-out PT-BR subset contains 14 cases. Evidence is in
`evidence/router-ptbr-hard.json` and the English-versus-multilingual comparison
is in `evidence/router-laya-multilingual.json`.

The official Laya page and Hugging Face model card document the public
multilingual checkpoint and bundled subfolder architecture.[6][4] The local
benchmark also loaded the multilingual subfolder on CUDA; no checkpoint was
silently substituted for the prior baseline.

The PT-BR safety results are measured evidence, not a general multilingual
claim. Further PT-BR hard-set expansion remains necessary before domain policy.

## Error taxonomy

The generated error taxonomy now distinguishes:

- `wrong_tool_inference`;
- `wrong_rag_inference`;
- `garbage_input`;
- `missing_context`;
- `unknown_intent`;
- `code_mixed_with_natural_language`;
- `language_failure`;
- `prompt_injection`;
- `unsafe_or_overlong`.

The most important remaining errors for the explicit Laya safety policy were
`wrong_tool_inference`, code mixed with natural language, and language failure.

## Recommendation

Do not start Fiscal Intelligence Platform automation yet.

Recommended current operating mode:

```text
Laya explicit + deterministic safety pre-gate
→ advisory route only
→ authorization/policy gate
→ human approval for sensitive actions
→ ABSTAIN when uncertain
```

The safety sprint demonstrates that Laya can continue as a fast decision layer,
but automatic sensitive routing remains gated by coverage, unsafe-route rate,
and deterministic authorization.

Sources: [6] https://laya.convaiinnovations.com · [4] https://huggingface.co/convaiinnovations/laya
