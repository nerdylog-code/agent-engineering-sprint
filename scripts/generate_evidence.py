"""Generate portfolio evidence from real local executions."""

from __future__ import annotations

import json
import math
import os
import statistics
from pathlib import Path

from agent_lab.models import AgentRequest
from agent_lab.orchestrator import AgentOrchestrator
from production_rag.dataset import build_golden_dataset, build_synthetic_corpus
from production_rag.evaluator import evaluate_modes
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def generate_agent_evidence() -> dict[str, object]:
    trace_path = EVIDENCE / "traces" / "agent-matrix.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text("", encoding="utf-8")
    cases = [
        ("calculate budget", "calcule 12 + 5", "calculator"),
        ("lookup engineering faq", "use a tool to explain retry", "lookup_faq"),
        ("retrieve evidence", "find a document citation", None),
        ("explain architecture", "give a concise overview", None),
        ("validate structured output", "hello", None),
        ("calculate another value", "calculate 9 * 9", "calculator"),
        ("retrieve another source", "retrieve rag evidence", None),
        ("explain security", "least privilege overview", None),
    ]
    results = []
    for objective, user_input, expected_tool in cases:
        result = AgentOrchestrator(trace_path=trace_path).run(
            AgentRequest(objective=objective, user_input=user_input)
        )
        results.append((result, expected_tool))
    successful = [result for result, _ in results if result.status == "completed"]
    tool_expected = [expected for _, expected in results if expected is not None]
    tool_matches = sum(
        result.route.selected_tool == expected
        for result, expected in results
        if expected is not None
    )
    structured_valid = sum(result.response is not None for result, _ in results)
    retries = sum(result.retries > 0 for result, _ in results)
    latencies_ms = [result.latency * 1000 for result, _ in results]
    trace_rows = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metrics = {
        "runs": len(results),
        "task_success_rate": round(len(successful) / len(results), 6),
        "tool_selection_accuracy": round(tool_matches / max(1, len(tool_expected)), 6),
        "structured_output_validity": round(structured_valid / len(results), 6),
        "retry_rate": round(retries / len(results), 6),
        "latency_p50_ms": round(statistics.median(latencies_ms), 6),
        "latency_p95_ms": round(_percentile(latencies_ms, 0.95), 6),
        "total_input_tokens": sum(row["input_tokens"] for row in trace_rows),
        "total_output_tokens": sum(row["output_tokens"] for row in trace_rows),
        "error_rate": round(sum(result.status == "failed" for result, _ in results) / len(results), 6),
        "model": "offline-deterministic-v1",
        "trace_file": str(trace_path.relative_to(ROOT)),
    }
    output = EVIDENCE / "metrics" / "agent_metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def generate_rag_evidence() -> dict[str, object]:
    documents = build_synthetic_corpus(100)
    dataset = build_golden_dataset(50)
    chunks = ingest_documents(documents)
    modes = evaluate_modes(HybridRetriever(chunks), dataset)
    output = EVIDENCE / "eval-results" / "rag_metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"documents": len(documents), "chunks": len(chunks), "questions": len(dataset), "modes": modes}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dataset_path = ROOT / "evals" / "golden_dataset.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "pass",
        "agent": generate_agent_evidence(),
        "rag": generate_rag_evidence(),
        "provenance": {
            "offline": True,
            "pythonpath": os.environ.get("PYTHONPATH", ""),
            "commands": [
                "PYTHONPATH=src python scripts/generate_evidence.py",
                "PYTHONPATH=src python scripts/ci.py --strict",
            ],
        },
    }
    output = EVIDENCE / "latest.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
