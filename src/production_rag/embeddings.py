"""Embedding backends: deterministic hashing control and real FastEmbed ONNX."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from .retrieval import hashed_embedding


class EmbeddingBackend(Protocol):
    name: str
    dimensions: int

    def embed_documents(self, texts: Iterable[str]) -> list[tuple[float, ...]]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...


class HashEmbeddingBackend:
    name = "hashing"

    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: Iterable[str]) -> list[tuple[float, ...]]:
        return [hashed_embedding(text, self.dimensions) for text in texts]

    def embed_query(self, text: str) -> tuple[float, ...]:
        return hashed_embedding(text, self.dimensions)


class FastEmbedBackend:
    name = "fastembed"

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-small-en-v1.5",
        cache_dir: str | Path | None = None,
        threads: int | None = None,
    ) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - optional dependency boundary
            raise RuntimeError("install the optional fastembed dependency first") from exc
        kwargs: dict[str, Any] = {"model_name": model_name}
        if cache_dir is not None:
            kwargs["cache_dir"] = str(cache_dir)
        if threads is not None:
            kwargs["threads"] = threads
        self._model = TextEmbedding(**kwargs)
        self.model_name = model_name
        self.dimensions = int(self._model.embedding_size)

    def embed_documents(self, texts: Iterable[str]) -> list[tuple[float, ...]]:
        return [tuple(float(value) for value in row) for row in self._model.passage_embed(list(texts))]

    def embed_query(self, text: str) -> tuple[float, ...]:
        row = next(iter(self._model.query_embed([text])))
        return tuple(float(value) for value in row)
