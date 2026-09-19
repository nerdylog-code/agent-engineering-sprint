"""Measured retrieval and answer-quality metrics."""

from __future__ import annotations

from collections.abc import Iterable
from statistics import mean
from typing import Any

from .retrieval import HybridRetriever, keyword_score, tokenize


def _document_ids(hits: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(hit.chunk.document_id for hit in hits))


def _question_metrics(retriever: HybridRetriever, row: dict[str, Any], *, mode: str, rerank: bool) -> dict[str, float]:
    hits = retriever.search(row["question"], top_k=5, mode=mode, rerank=rerank)
    ids = _document_ids(hits)
    expected = str(row["expected_document"])
    rank = ids.index(expected) + 1 if expected in ids else None
    context = " ".join(hit.chunk.text for hit in hits)
    terms = [str(term) for term in row.get("expected_terms", [])]
    term_recall = sum(1 for term in terms if term.lower() in context.lower()) / max(1, len(terms))
    return {
        "recall_at_1": float(bool(rank and rank <= 1)),
        "recall_at_3": float(bool(rank and rank <= 3)),
        "recall_at_5": float(bool(rank and rank <= 5)),
        "mrr": 1.0 / rank if rank else 0.0,
        "groundedness": term_recall,
        "answer_relevance": keyword_score(tokenize(row["question"]), context),
    }


def evaluate_retrieval(
    retriever: HybridRetriever,
    dataset: list[dict[str, Any]],
    *,
    mode: str = "hybrid",
    rerank: bool = True,
) -> dict[str, Any]:
    if not dataset:
        raise ValueError("dataset must not be empty")
    rows = [_question_metrics(retriever, row, mode=mode, rerank=rerank) for row in dataset]
    metric_names = tuple(rows[0])
    metrics = {name: round(mean(row[name] for row in rows), 6) for name in metric_names}
    return {"mode": mode, "rerank": rerank, "questions": len(rows), **metrics}


def evaluate_modes(retriever: HybridRetriever, dataset: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "vector_only": evaluate_retrieval(retriever, dataset, mode="vector", rerank=False),
        "hybrid": evaluate_retrieval(retriever, dataset, mode="hybrid", rerank=False),
        "hybrid_reranker": evaluate_retrieval(retriever, dataset, mode="hybrid", rerank=True),
    }
