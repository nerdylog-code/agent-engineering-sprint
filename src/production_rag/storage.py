"""Transactional SQLite persistence for documents and chunks."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import Chunk, Document


class SQLiteCorpusStore:
    """Persist a versioned corpus so retrieval can survive process restarts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    text TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, position);
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def replace(self, documents: Iterable[Document], chunks: Iterable[Chunk]) -> None:
        docs = list(documents)
        rows = list(chunks)
        with self._connection() as connection:
            connection.execute("DELETE FROM chunks")
            connection.execute("DELETE FROM documents")
            connection.executemany(
                "INSERT INTO documents(document_id, title, text, metadata_json) VALUES (?, ?, ?, ?)",
                [
                    (doc.document_id, doc.title, doc.text, json.dumps(doc.metadata, ensure_ascii=False))
                    for doc in docs
                ],
            )
            connection.executemany(
                "INSERT INTO chunks(chunk_id, document_id, text, position, metadata_json) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.text,
                        chunk.position,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in rows
                ],
            )

    def counts(self) -> dict[str, int]:
        with self._connection() as connection:
            documents = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
            chunks = int(connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        return {"documents": documents, "chunks": chunks}

    def load_chunks(self) -> list[Chunk]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT chunk_id, document_id, text, position, metadata_json FROM chunks ORDER BY document_id, position"
            ).fetchall()
        return [
            Chunk(
                chunk_id=row[0],
                document_id=row[1],
                text=row[2],
                position=row[3],
                metadata=json.loads(row[4]),
            )
            for row in rows
        ]
