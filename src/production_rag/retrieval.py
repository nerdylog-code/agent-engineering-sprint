"""Dependency-free vector, keyword, fusion, and reranking retrieval."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING, TypedDict

from .models import Chunk, RagAnswer, RetrievalHit

if TYPE_CHECKING:
    from agent_lab.telemetry import Telemetry

    from .embeddings import EmbeddingBackend

_TOKEN_RE = re.compile(r"[a-z0-9À-ÿ_-]+", re.IGNORECASE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "the", "this", "to", "what", "which", "why", "with",
    "um", "uma", "e", "em", "de", "da", "dos", "das", "o", "os", "que", "qual", "quais",
    "por", "para", "como", "se", "não", "na", "no", "nas", "nos", "após", "sobre",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def hashed_embedding(text: str, dimensions: int = 128) -> tuple[float, ...]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return tuple(vector)
    return tuple(value / norm for value in vector)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


def keyword_score(query_tokens: list[str], text: str) -> float:
    content_tokens = {token for token in query_tokens if token not in _STOPWORDS}
    if not content_tokens:
        return 0.0
    counts = Counter(tokenize(text))
    matched = sum(1 for token in content_tokens if counts[token])
    return matched / len(content_tokens)


class ScoreRow(TypedDict, total=False):
    chunk: Chunk
    vector: float
    keyword: float
    fusion: float
    rerank: float


class HybridRetriever:
    def __init__(
        self,
        chunks: Iterable[Chunk],
        *,
        dimensions: int = 128,
        embedding_backend: EmbeddingBackend | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.chunks = tuple(chunks)
        if embedding_backend is None:
            from .embeddings import HashEmbeddingBackend

            embedding_backend = HashEmbeddingBackend(dimensions)
        self.embedding_backend = embedding_backend
        self.telemetry = telemetry
        self.dimensions = embedding_backend.dimensions
        vectors = embedding_backend.embed_documents(chunk.text for chunk in self.chunks)
        self.embeddings = {
            chunk.chunk_id: vector for chunk, vector in zip(self.chunks, vectors, strict=True)
        }

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        mode: str = "hybrid",
        rerank: bool = True,
        tenant_id: str | None = None,
        principal: str | None = None,
    ) -> list[RetrievalHit]:
        if self.telemetry is not None:
            with self.telemetry.span("retrieval.search", {"tenant_id": tenant_id, "mode": mode}):
                return self._search(
                    query,
                    top_k=top_k,
                    mode=mode,
                    rerank=rerank,
                    tenant_id=tenant_id,
                    principal=principal,
                )
        return self._search(
            query,
            top_k=top_k,
            mode=mode,
            rerank=rerank,
            tenant_id=tenant_id,
            principal=principal,
        )

    def _search(
        self,
        query: str,
        *,
        top_k: int,
        mode: str,
        rerank: bool,
        tenant_id: str | None,
        principal: str | None,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if mode not in {"vector", "keyword", "hybrid"}:
            raise ValueError("mode must be vector, keyword, or hybrid")
        query_tokens = tokenize(query)
        query_vector = self.embedding_backend.embed_query(query)
        scored: list[ScoreRow] = []
        for chunk in self.chunks:
            if not self._allowed(chunk, tenant_id=tenant_id, principal=principal):
                continue
            vector = cosine(query_vector, self.embeddings[chunk.chunk_id])
            lexical = keyword_score(query_tokens, chunk.text)
            scored.append({"chunk": chunk, "vector": vector, "keyword": lexical})

        vector_rank = {
            row["chunk"].chunk_id: rank
            for rank, row in enumerate(sorted(scored, key=lambda r: r["vector"], reverse=True), start=1)
        }
        keyword_rank = {
            row["chunk"].chunk_id: rank
            for rank, row in enumerate(sorted(scored, key=lambda r: r["keyword"], reverse=True), start=1)
        }
        for row in scored:
            chunk = row["chunk"]
            row["fusion"] = 1.0 / (60 + vector_rank[chunk.chunk_id]) + 1.0 / (60 + keyword_rank[chunk.chunk_id])
            row["rerank"] = self._rerank_score(query_tokens, chunk, row["vector"], row["keyword"])

        if mode == "vector":
            key = lambda r: (r["vector"], r["keyword"])
        elif mode == "keyword":
            key = lambda r: (r["keyword"], r["vector"])
        else:
            key = lambda r: (r["rerank"] if rerank else r["fusion"], r["keyword"])
        ordered = sorted(scored, key=key, reverse=True)[:top_k]
        return [
            RetrievalHit(
                chunk=row["chunk"],
                vector_score=round(row["vector"], 6),
                keyword_score=round(row["keyword"], 6),
                fusion_score=round(row["fusion"], 6),
                rerank_score=round(row["rerank"], 6),
            )
            for row in ordered
        ]

    @staticmethod
    def _rerank_score(query_tokens: list[str], chunk: Chunk, vector: float, keyword: float) -> float:
        text_tokens = tokenize(chunk.text)
        query_set = set(query_tokens)
        phrase_bonus = 0.15 if " ".join(query_tokens[:2]) in chunk.text.lower() else 0.0
        exact_marker_bonus = 0.35 if any(token.startswith("fact-") and token in text_tokens for token in query_set) else 0.0
        return 0.35 * max(0.0, vector) + 0.5 * keyword + phrase_bonus + exact_marker_bonus

    def answer(
        self,
        query: str,
        *,
        top_k: int = 5,
        tenant_id: str | None = None,
        principal: str | None = None,
    ) -> RagAnswer:
        hits = tuple(
            self.search(
                query,
                top_k=top_k,
                mode="hybrid",
                rerank=True,
                tenant_id=tenant_id,
                principal=principal,
            )
        )
        max_keyword_score = max((hit.keyword_score for hit in hits), default=0.0)
        if not hits or max_keyword_score < 0.25:
            return RagAnswer(query, "Não encontrei evidência local suficiente.", (), 0.0, 0.0, hits)
        top = hits[0]
        citations = tuple(dict.fromkeys(hit.chunk.document_id for hit in hits))
        answer = f"{top.chunk.text} [{top.chunk.document_id}]"
        context_tokens = set(tokenize(" ".join(hit.chunk.text for hit in hits)))
        answer_tokens = set(tokenize(answer))
        grounded = len(answer_tokens & context_tokens) / max(1, len(answer_tokens))
        relevance = keyword_score(tokenize(query), " ".join(hit.chunk.text for hit in hits))
        return RagAnswer(query, answer, citations, round(grounded, 6), round(relevance, 6), hits)

    @staticmethod
    def _allowed(chunk: Chunk, *, tenant_id: str | None, principal: str | None) -> bool:
        metadata = chunk.metadata
        document_tenant = metadata.get("tenant_id")
        if document_tenant is not None and document_tenant != tenant_id:
            return False
        allowed = metadata.get("allowed_principals")
        return allowed is None or principal in {item.strip() for item in allowed.split(",") if item.strip()}
