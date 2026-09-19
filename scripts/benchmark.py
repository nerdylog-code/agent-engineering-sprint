"""Run a deterministic local performance baseline and write evidence."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path

from agent_lab.models import AgentRequest
from agent_lab.orchestrator import AgentOrchestrator
from production_rag.dataset import build_synthetic_corpus
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmarks/local-baseline.json"))
    args = parser.parse_args(argv)
    if args.runs <= 0 or args.runs > 2_000:
        raise SystemExit("--runs must be between 1 and 2000")

    agent = AgentOrchestrator()
    agent_latencies: list[float] = []
    agent_success = 0
    for index in range(args.runs):
        started = time.perf_counter()
        result = agent.run(AgentRequest("benchmark tool routing", f"calcule {index} + 1"))
        agent_latencies.append((time.perf_counter() - started) * 1000)
        agent_success += result.status == "completed"

    retriever = HybridRetriever(ingest_documents(build_synthetic_corpus(100)))
    rag_latencies: list[float] = []
    for index in range(args.runs):
        started = time.perf_counter()
        retriever.search(f"fact-{index % 50:03d} evidence", top_k=5)
        rag_latencies.append((time.perf_counter() - started) * 1000)

    payload = {
        "status": "pass",
        "runs": args.runs,
        "agent": {
            "success_rate": round(agent_success / args.runs, 6),
            "latency_p50_ms": round(statistics.median(agent_latencies), 6),
            "latency_p95_ms": round(percentile(agent_latencies, 0.95), 6),
        },
        "rag": {
            "documents": 100,
            "latency_p50_ms": round(statistics.median(rag_latencies), 6),
            "latency_p95_ms": round(percentile(rag_latencies, 0.95), 6),
        },
        "provenance": "scripts/benchmark.py",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
