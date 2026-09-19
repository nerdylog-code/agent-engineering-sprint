"""Document parsing and overlapping chunking."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .models import Chunk, Document


def chunk_text(document: Document, *, chunk_size: int = 48, overlap: int = 8) -> list[Chunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be in [0, chunk_size)")
    words = document.text.split()
    if not words:
        return []
    step = chunk_size - overlap
    chunks: list[Chunk] = []
    for start in range(0, len(words), step):
        text = " ".join(words[start : start + chunk_size])
        chunks.append(
            Chunk(
                chunk_id=f"{document.document_id}#chunk-{len(chunks):03d}",
                document_id=document.document_id,
                text=text,
                position=len(chunks),
                metadata=document.metadata,
            )
        )
        if start + chunk_size >= len(words):
            break
    return chunks


def ingest_documents(documents: Iterable[Document], *, chunk_size: int = 48, overlap: int = 8) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_text(document, chunk_size=chunk_size, overlap=overlap))
    return chunks


def load_documents(path: str | Path) -> list[Document]:
    root = Path(path)
    documents: list[Document] = []
    for item in sorted(root.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in {".txt", ".md", ".json"}:
            continue
        if item.suffix.lower() == ".json":
            payload = json.loads(item.read_text(encoding="utf-8"))
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                documents.append(
                    Document(
                        document_id=str(row["document_id"]),
                        title=str(row.get("title", row["document_id"])),
                        text=str(row["text"]),
                        metadata={str(k): str(v) for k, v in row.get("metadata", {}).items()},
                    )
                )
        else:
            documents.append(
                Document(
                    document_id=item.stem,
                    title=item.stem,
                    text=item.read_text(encoding="utf-8"),
                    metadata={"path": str(item)},
                )
            )
    return documents
