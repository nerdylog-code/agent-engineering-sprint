"""Measure hashing control versus a real FastEmbed ONNX backend."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from pathlib import Path

from production_rag.dataset import build_golden_dataset, build_synthetic_corpus
from production_rag.embeddings import FastEmbedBackend, HashEmbeddingBackend
from production_rag.evaluator import evaluate_retrieval
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))]


def folder_size(path: Path) -> int | None:
    if not path.exists():
        return None
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def rss_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except ImportError:
        return None


def measure(
    name: str,
    retriever: HybridRetriever,
    dataset: list[dict[str, object]],
    runs: int,
    *,
    memory_before_bytes: int | None,
    memory_after_bytes: int | None,
) -> dict[str, object]:
    query_times: list[float] = []
    for row in dataset[:runs]:
        started = time.perf_counter()
        retriever.search(str(row["question"]), top_k=5, mode="hybrid", rerank=True)
        query_times.append((time.perf_counter() - started) * 1000)
    metrics = evaluate_retrieval(retriever, dataset, mode="hybrid", rerank=True)
    return {
        "backend": name,
        "dimensions": retriever.dimensions,
        "float32_index_bytes": sum(len(vector) * 4 for vector in retriever.embeddings.values()),
        "memory_rss_before_bytes": memory_before_bytes,
        "memory_rss_after_bytes": memory_after_bytes,
        "memory_rss_delta_bytes": (
            memory_after_bytes - memory_before_bytes
            if memory_before_bytes is not None and memory_after_bytes is not None
            else None
        ),
        "questions_evaluated": len(dataset),
        "query_runs": len(query_times),
        "recall_at_1": metrics["recall_at_1"],
        "recall_at_3": metrics["recall_at_3"],
        "recall_at_5": metrics["recall_at_5"],
        "mrr": metrics["mrr"],
        "groundedness": metrics["groundedness"],
        "answer_relevance": metrics["answer_relevance"],
        "latency_p50_ms": round(statistics.median(query_times), 6),
        "latency_p95_ms": round(percentile(query_times, 0.95), 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmarks/embedding-comparison.json"))
    args = parser.parse_args(argv)
    if args.runs <= 0 or args.runs > 50:
        raise SystemExit("--runs must be between 1 and 50")

    documents = build_synthetic_corpus(100)
    chunks = ingest_documents(documents)
    dataset = build_golden_dataset(50)
    hash_memory_before = rss_bytes()
    hash_started = time.perf_counter()
    hash_retriever = HybridRetriever(chunks, embedding_backend=HashEmbeddingBackend())
    hash_build_ms = (time.perf_counter() - hash_started) * 1000
    hash_memory_after = rss_bytes()

    cache_dir = Path(os.environ.get("FASTEMBED_CACHE_PATH", "evidence/runtime/fastembed-cache"))
    fast_memory_before = rss_bytes()
    fast_started = time.perf_counter()
    fast_backend = FastEmbedBackend(model_name=args.model, cache_dir=cache_dir)
    fast_retriever = HybridRetriever(chunks, embedding_backend=fast_backend)
    fast_build_ms = (time.perf_counter() - fast_started) * 1000
    fast_memory_after = rss_bytes()
    payload = {
        "status": "pass",
        "documents": len(documents),
        "chunks": len(chunks),
        "model": args.model,
        "hashing": {
            "build_latency_ms": round(hash_build_ms, 6),
            **measure(
                "hashing",
                hash_retriever,
                dataset,
                args.runs,
                memory_before_bytes=hash_memory_before,
                memory_after_bytes=hash_memory_after,
            ),
        },
        "fastembed": {
            "build_latency_ms": round(fast_build_ms, 6),
            "cache_size_bytes": folder_size(cache_dir),
            **measure(
                "fastembed",
                fast_retriever,
                dataset,
                args.runs,
                memory_before_bytes=fast_memory_before,
                memory_after_bytes=fast_memory_after,
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
