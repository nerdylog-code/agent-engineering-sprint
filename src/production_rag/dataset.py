"""Synthetic corpus and golden questions for reproducible local evaluation."""

from __future__ import annotations

from .models import Document

_TOPICS: tuple[tuple[str, str, str], ...] = (
    ("observability", "tracing", "A trace connects router, model, and tool spans using one trace identifier."),
    ("evaluation", "deterministic-eval", "A deterministic evaluator is repeatable and does not require an LLM judge."),
    ("retrieval", "hybrid-search", "Hybrid retrieval combines lexical evidence with semantic similarity before reranking."),
    ("security", "least-privilege", "Least privilege keeps each tool limited to the smallest permission it needs."),
    ("mcp", "mcp-boundary", "MCP separates host, client, and server responsibilities around tool execution."),
    ("reliability", "bounded-retry", "Retries must be bounded and should protect non-idempotent operations from duplication."),
    ("structured-output", "schema-validation", "Schema validation turns an untrusted model response into an explicit contract."),
    ("ci-cd", "pipeline-gates", "A CI pipeline should run tests, type or syntax checks, security checks, and packaging gates."),
    ("rag", "groundedness", "Groundedness measures whether an answer is supported by retrieved context and citations."),
    ("performance", "p95-latency", "P95 latency reveals slow-tail behavior that an average can hide."),
)


def build_synthetic_corpus(count: int = 100) -> list[Document]:
    if count <= 0:
        raise ValueError("count must be positive")
    documents: list[Document] = []
    for index in range(count):
        topic, concept, statement = _TOPICS[index % len(_TOPICS)]
        document_id = f"doc-{index:03d}"
        marker = f"fact-{index:03d}"
        text = (
            f"{statement} This document records {marker} for the {topic} topic. "
            f"The canonical concept is {concept}. Evidence is local, versioned, and reviewable."
        )
        documents.append(
            Document(
                document_id=document_id,
                title=f"{topic.title()} note {index:03d}",
                text=text,
                metadata={"topic": topic, "concept": concept, "marker": marker},
            )
        )
    return documents


def build_golden_dataset(question_count: int = 50) -> list[dict[str, object]]:
    if question_count <= 0:
        raise ValueError("question_count must be positive")
    questions: list[dict[str, object]] = []
    for index in range(question_count):
        topic, concept, _statement = _TOPICS[index % len(_TOPICS)]
        document_id = f"doc-{index:03d}"
        marker = f"fact-{index:03d}"
        questions.append(
            {
                "id": f"q-{index:03d}",
                "question": f"What is the verified {marker} about {topic} and {concept}?",
                "expected_document": document_id,
                "expected_terms": [marker, topic, concept],
                "expected_answer": marker,
            }
        )
    return questions
