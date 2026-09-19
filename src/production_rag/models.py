"""RAG data structures and deterministic synthetic corpus generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Document:
    document_id: str
    title: str
    text: str
    metadata: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    position: int
    metadata: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    vector_score: float
    keyword_score: float
    fusion_score: float
    rerank_score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "text": self.chunk.text,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "fusion_score": self.fusion_score,
            "rerank_score": self.rerank_score,
        }


@dataclass(frozen=True)
class RagAnswer:
    query: str
    answer: str
    citations: tuple[str, ...]
    groundedness: float
    answer_relevance: float
    hits: tuple[RetrievalHit, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "answer": self.answer,
            "citations": list(self.citations),
            "groundedness": self.groundedness,
            "answer_relevance": self.answer_relevance,
            "hits": [hit.to_dict() for hit in self.hits],
        }
