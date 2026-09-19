"""Durable, redacted trace persistence for local and service deployments."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import TraceEvent


class SQLiteTraceStore:
    """Small SQLite sink with WAL mode and indexed trace/run lookup."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_trace_events_trace ON trace_events(trace_id, id);
                CREATE INDEX IF NOT EXISTS idx_trace_events_run ON trace_events(run_id, id);
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    def append(self, events: Iterable[TraceEvent]) -> None:
        rows = list(events)
        if not rows:
            return
        with self._connection() as connection:
            connection.executemany(
                "INSERT INTO trace_events(trace_id, run_id, event, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        event.trace_id,
                        event.run_id,
                        event.event,
                        event.status,
                        json.dumps(event.to_dict(), ensure_ascii=False),
                        event.timestamp,
                    )
                    for event in rows
                ],
            )

    def count(self, *, trace_id: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM trace_events"
        params: tuple[str, ...] = ()
        if trace_id:
            query += " WHERE trace_id = ?"
            params = (trace_id,)
        with self._connection() as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def read(self, trace_id: str) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM trace_events WHERE trace_id = ? ORDER BY id", (trace_id,)
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
