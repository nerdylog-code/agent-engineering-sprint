"""Benchmark embeddings on an adversarial semantic retrieval dataset."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from production_rag.adversarial import build_adversarial_corpus, build_adversarial_dataset
from production_rag.embeddings import FastEmbedBackend, HashEmbeddingBackend
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))]


def rss_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except ImportError:
        return None


def folder_size(path: Path) -> int | None:
    if not path.exists():
        return None
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def evaluate_backend(
    name: str,
    retriever: HybridRetriever,
    dataset: list[dict[str, object]],
    *,
    build_latency_ms: float,
    memory_before_bytes: int | None,
    memory_after_bytes: int | None,
) -> dict[str, object]:
    query_times: list[float] = []
    answerable_rows: list[dict[str, object]] = []
    unanswerable_rows: list[dict[str, object]] = []
    category_rows: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in dataset:
        started = time.perf_counter()
        hits = retriever.search(str(row["question"]), top_k=5, mode="vector", rerank=False)
        query_times.append((time.perf_counter() - started) * 1000)
        document_ids = [hit.chunk.document_id for hit in hits]
        expected = row["expected_document"]
        if expected is not None:
            rank = document_ids.index(str(expected)) + 1 if str(expected) in document_ids else None
            metrics = {
                "recall_at_1": float(bool(rank and rank <= 1)),
                "recall_at_3": float(bool(rank and rank <= 3)),
                "recall_at_5": float(bool(rank and rank <= 5)),
                "mrr": 1.0 / rank if rank else 0.0,
            }
            answerable_rows.append(metrics)
            category_rows[str(row["category"])].append(metrics)
        else:
            answer = retriever.answer(str(row["question"]), top_k=5)
            unanswerable_rows.append(
                {
                    "abstained": float(not bool(answer.citations)),
                    "false_positive": float(bool(answer.citations)),
                }
            )

    def average(rows: list[dict[str, float]], key: str) -> float:
        return round(statistics.mean(row[key] for row in rows), 6) if rows else 0.0

    categories = {
        category: {
            "questions": len(rows),
            "recall_at_1": average(rows, "recall_at_1"),
            "recall_at_3": average(rows, "recall_at_3"),
            "recall_at_5": average(rows, "recall_at_5"),
            "mrr": average(rows, "mrr"),
        }
        for category, rows in sorted(category_rows.items())
    }
    unanswerable_count = len(unanswerable_rows)
    return {
        "backend": name,
        "retrieval_mode": "vector_only",
        "dimensions": retriever.dimensions,
        "questions": len(dataset),
        "answerable_questions": len(answerable_rows),
        "unanswerable_questions": unanswerable_count,
        "recall_at_1": average(answerable_rows, "recall_at_1"),
        "recall_at_3": average(answerable_rows, "recall_at_3"),
        "recall_at_5": average(answerable_rows, "recall_at_5"),
        "mrr": average(answerable_rows, "mrr"),
        "abstention_rate": round(
            statistics.mean(row["abstained"] for row in unanswerable_rows), 6
        )
        if unanswerable_rows
        else 0.0,
        "false_positive_rate": round(
            statistics.mean(row["false_positive"] for row in unanswerable_rows), 6
        )
        if unanswerable_rows
        else 0.0,
        "latency_p50_ms": round(statistics.median(query_times), 6),
        "latency_p95_ms": round(percentile(query_times, 0.95), 6),
        "build_latency_ms": round(build_latency_ms, 6),
        "float32_index_bytes": sum(len(vector) * 4 for vector in retriever.embeddings.values()),
        "memory_rss_before_bytes": memory_before_bytes,
        "memory_rss_after_bytes": memory_after_bytes,
        "memory_rss_delta_bytes": (
            memory_after_bytes - memory_before_bytes
            if memory_before_bytes is not None and memory_after_bytes is not None
            else None
        ),
        "category_metrics": categories,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmarks/adversarial-embedding-comparison.json"))
    parser.add_argument("--dataset-output", type=Path, default=Path("evals/adversarial_dataset.json"))
    args = parser.parse_args(argv)

    documents = build_adversarial_corpus()
    dataset = build_adversarial_dataset()
    chunks = ingest_documents(documents, chunk_size=128, overlap=16)
    args.dataset_output.parent.mkdir(parents=True, exist_ok=True)
    args.dataset_output.write_text(
        json.dumps(
            {
                "description": "Adversarial semantic retrieval benchmark; original lexical baseline remains separate.",
                "documents": [document.to_dict() for document in documents],
                "questions": dataset,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    hash_before = rss_bytes()
    started = time.perf_counter()
    hash_retriever = HybridRetriever(chunks, embedding_backend=HashEmbeddingBackend())
    hash_build_ms = (time.perf_counter() - started) * 1000
    hash_after = rss_bytes()

    cache_dir = Path(os.environ.get("FASTEMBED_CACHE_PATH", "evidence/runtime/fastembed-cache"))
    fast_before = rss_bytes()
    started = time.perf_counter()
    fast_retriever = HybridRetriever(
        chunks,
        embedding_backend=FastEmbedBackend(model_name=args.model, cache_dir=cache_dir),
    )
    fast_build_ms = (time.perf_counter() - started) * 1000
    fast_after = rss_bytes()

    payload: dict[str, Any] = {
        "status": "pass",
        "methodology": {
            "corpus_documents": len(documents),
            "chunks": len(chunks),
            "questions": len(dataset),
            "answerable_questions": sum(row["expected_document"] is not None for row in dataset),
            "unanswerable_questions": sum(row["expected_document"] is None for row in dataset),
            "retrieval_mode": "vector_only",
            "why": "isolates embedding quality from lexical fusion/reranker bonuses",
            "model": args.model,
        },
        "hashing": evaluate_backend(
            "hashing",
            hash_retriever,
            dataset,
            build_latency_ms=hash_build_ms,
            memory_before_bytes=hash_before,
            memory_after_bytes=hash_after,
        ),
        "fastembed": {
            **evaluate_backend(
                "fastembed",
                fast_retriever,
                dataset,
                build_latency_ms=fast_build_ms,
                memory_before_bytes=fast_before,
                memory_after_bytes=fast_after,
            ),
            "model_cache_size_bytes": folder_size(cache_dir),
        },
        "limitations": [
            "FastEmbed model is BGE-small English; multilingual results are exploratory.",
            "RSS is process-level and includes ONNX runtime allocations.",
            "A 54-question benchmark is evidence of relative behavior, not production capacity.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
