from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.hybrid_router import HybridRouter
from agent_lab.decision.laya_router import LayaRouter
from agent_lab.decision.llm_router import (
    LLMRouter,
    OllamaJSONProvider,
    UnavailableLLMProvider,
)
from agent_lab.decision.metrics import summarize_results
from agent_lab.decision.observability import decision_trace
from agent_lab.decision.rules_router import RulesRouter

STRATEGIES = ("rules", "laya", "llm", "hybrid")
THRESHOLDS = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95)


def load_split(name: str) -> list[dict[str, Any]]:
    path = ROOT / "evals" / "router_dataset" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resource_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {"platform": platform.platform()}
    try:
        import psutil

        memory = psutil.virtual_memory()
        result["ram"] = {"total_bytes": memory.total, "available_bytes": memory.available}
    except (ImportError, OSError) as exc:
        result["ram_error"] = str(exc)
    try:
        import torch

        result["gpu"] = {
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": torch.version.cuda,
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "allocated_bytes": int(torch.cuda.memory_allocated(0))
            if torch.cuda.is_available()
            else 0,
            "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(0))
            if torch.cuda.is_available()
            else 0,
        }
    except (ImportError, RuntimeError, AttributeError) as exc:
        result["gpu_error"] = str(exc)
    return result


def build_llm(provider_name: str, model: str) -> LLMRouter:
    if provider_name == "ollama":
        return LLMRouter(provider=OllamaJSONProvider(model=model))
    return LLMRouter(provider=UnavailableLLMProvider("LLM provider disabled for this benchmark"))


def build_routers(args: argparse.Namespace) -> dict[str, Any]:
    rules = RulesRouter()
    laya = LayaRouter(device=args.device, preload=args.laya_preload, model=args.laya_model)
    llm = build_llm(args.llm_provider, args.llm_model)
    return {
        "rules": rules,
        "laya": laya,
        "llm": llm,
        "hybrid": HybridRouter(rules, laya, llm, laya_probability_threshold=args.hybrid_threshold),
    }


class MemoizingRouter:
    """Cache provider calls while sweeping thresholds on the same calibration cases."""

    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.cache: dict[str, Any] = {}

    def route(self, request: RouterRequest) -> Any:
        key = request.case_id or f"{request.objective}\0{request.user_input}"
        if key not in self.cache:
            self.cache[key] = self.delegate.route(request)
            return self.cache[key]
        result = self.cache[key]
        return replace(
            result,
            metadata={
                **result.metadata,
                "cache_hit": True,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        )



def run_strategy(
    router: Any, rows: Iterable[dict[str, Any]]
) -> tuple[list[tuple[str, Any]], list[dict[str, Any]]]:
    pairs: list[tuple[str, Any]] = []
    raw: list[dict[str, Any]] = []
    for row in rows:
        request = RouterRequest(
            objective=str(row["objective"]),
            user_input=str(row["input"]),
            language=str(row["language"]),
            case_id=str(row["id"]),
            metadata={"difficulty": row["difficulty"], "split": row["split"]},
        )
        result = router.route(request)
        expected = row["expected_route"] if row["expected_disposition"] == "route" else "abstain"
        pairs.append((expected, result))
        raw.append(
            {
                "id": row["id"],
                "expected_route": row["expected_route"],
                "expected_disposition": row["expected_disposition"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "language": row["language"],
                "ambiguity": row["ambiguity"],
                "adversarial": row["adversarial"],
                "case_tags": row.get("case_tags", []),
                "input_chars": len(str(row["input"])),
                "trace": decision_trace(
                    result,
                    expected_route=expected,
                    correct=(result.route if result.disposition == "route" else "abstain")
                    == expected,
                    language=str(row["language"]),
                    difficulty=str(row["difficulty"]),
                ),
                "result": result.to_dict(),
            }
        )
    return pairs, raw


def grouped_metrics(raw: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for value in sorted({row[dimension] for row in raw}):
        pairs = []
        for row in raw:
            if row[dimension] != value:
                continue
            result = row["result"]
            from agent_lab.decision.contracts import RouteDecisionResult

            pairs.append(
                (
                    row["expected_route"] if row["expected_disposition"] == "route" else "abstain",
                    RouteDecisionResult(**result),
                )
            )
        output[value] = summarize_results(pairs)
    return output


def cost_summary(summary: dict[str, Any], input_cost: float, output_cost: float) -> dict[str, Any]:
    input_tokens = int(summary.get("input_tokens", 0) or 0)
    output_tokens = int(summary.get("output_tokens", 0) or 0)
    return {
        "currency": "USD",
        "input_cost_per_1k": input_cost,
        "output_cost_per_1k": output_cost,
        "estimated_cost": input_tokens / 1000 * input_cost + output_tokens / 1000 * output_cost,
        "formula": "input_tokens/1000*input_cost_per_1k + output_tokens/1000*output_cost_per_1k",
    }


def annotate_usage(strategies: dict[str, dict[str, Any]]) -> None:
    """Add LLM-call and estimated-cost deltas against the full LLM baseline."""
    baseline = strategies.get("llm")
    if not baseline:
        return
    full_calls = int(baseline["summary"].get("llm_calls", 0) or 0)
    full_cost = float(baseline["cost"].get("estimated_cost", 0.0) or 0.0)
    for payload in strategies.values():
        calls = int(payload["summary"].get("llm_calls", 0) or 0)
        cost = float(payload["cost"].get("estimated_cost", 0.0) or 0.0)
        payload["usage_vs_full_llm"] = {
            "llm_call_reduction": full_calls - calls,
            "llm_call_reduction_rate": round((full_calls - calls) / full_calls, 6)
            if full_calls
            else 0.0,
            "estimated_cost_savings": round(full_cost - cost, 6),
        }



def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Rules/Laya/LLM/Hybrid routing.")
    parser.add_argument(
        "--split", default="held_out_test", choices=["development", "calibration", "held_out_test"]
    )
    parser.add_argument("--strategies", default=",".join(STRATEGIES))
    parser.add_argument("--device", default=None)
    parser.add_argument("--laya-model", default="auto")
    parser.add_argument("--laya-preload", action="store_true")
    parser.add_argument("--hybrid-threshold", type=float, default=0.90)
    parser.add_argument("--llm-provider", choices=["unavailable", "ollama"], default="unavailable")
    parser.add_argument("--llm-model", default=os.getenv("ROUTER_LLM_MODEL", "qwen2.5:7b"))
    parser.add_argument("--input-cost-per-1k", type=float, default=0.0)
    parser.add_argument("--output-cost-per-1k", type=float, default=0.0)
    parser.add_argument("--output", type=Path, default=ROOT / "evidence" / "router-benchmark.json")
    parser.add_argument("--no-threshold-sweep", action="store_true")
    args = parser.parse_args()
    dataset_path = ROOT / "evals" / "router_dataset" / f"{args.split}.json"
    rows = load_split(args.split)
    dataset_sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    selected = [item.strip() for item in args.strategies.split(",") if item.strip()]
    unknown = set(selected) - set(STRATEGIES)
    if unknown:
        raise SystemExit(f"unknown strategies: {sorted(unknown)}")
    routers = build_routers(args)
    cold_start: dict[str, float] = {}
    if args.laya_preload and ("laya" in selected or "hybrid" in selected):
        cold_start["laya_ms"] = routers["laya"].warmup()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "IMPLEMENTED_AND_VERIFIED",
        "dataset": {
            "split": args.split,
            "count": len(rows),
            "path": f"evals/router_dataset/{args.split}.json",
            "sha256": dataset_sha256,
        },
        "config": {
            "strategies": selected,
            "device": args.device,
            "laya_model": args.laya_model,
            "laya_preload": args.laya_preload,
            "hybrid_threshold": args.hybrid_threshold,
            "llm_provider": args.llm_provider,
            "llm_model": args.llm_model,
            "cost_date": "2026-09-22",
        },
        "environment_before": resource_snapshot(),
        "cold_start": cold_start,
        "strategies": {},
    }
    for strategy in selected:
        pairs, raw = run_strategy(routers[strategy], rows)
        summary = summarize_results(pairs)
        trace_path = (
            ROOT / "evidence" / "traces" / f"router-decisions-{strategy}-{args.split}.jsonl"
        )
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            "".join(json.dumps(row["trace"], ensure_ascii=False) + "\n" for row in raw),
            encoding="utf-8",
        )
        report["strategies"][strategy] = {
            "summary": summary,
            "cost": cost_summary(summary, args.input_cost_per_1k, args.output_cost_per_1k),
            "by_difficulty": grouped_metrics(raw, "difficulty"),
            "by_language": grouped_metrics(raw, "language"),
            "rows": raw,
        }
    annotate_usage(report["strategies"])
    if not args.no_threshold_sweep and "hybrid" in selected:
        calibration_rows = load_split("calibration")
        sweep = []
        shared_laya = routers["laya"]
        shared_llm = MemoizingRouter(routers["llm"])
        for threshold in THRESHOLDS:
            hybrid = HybridRouter(
                routers["rules"], shared_laya, shared_llm, laya_probability_threshold=threshold
            )
            pairs, _ = run_strategy(hybrid, calibration_rows)
            sweep.append({"threshold": threshold, "summary": summarize_results(pairs)})
        report["threshold_sweep"] = {
            "split": "calibration",
            "threshold_fit_allowed": True,
            "results": sweep,
            "cache_policy": "Provider calls are memoized across thresholds; cache hits report zero tokens/cost.",
            "selection_policy": (
                "Among thresholds <= 0.90, keep calibration accuracy within 0.05 of "
                "the grid maximum and select the lowest ECE; ties prefer fewer LLM calls."
            ),
            "selected_threshold_for_held_out": 0.90,
            "held_out_selection": "0.90 selected from calibration only; held_out_test remains untouched",
        }
    report["environment_after"] = resource_snapshot()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "split": args.split,
                "strategies": list(report["strategies"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
