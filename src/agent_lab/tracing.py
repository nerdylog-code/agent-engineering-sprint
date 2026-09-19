"""JSONL tracing with the fields needed for offline evaluation."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import TraceEvent

_SECRET_RE = re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^,\s}]+")


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _SECRET_RE.sub(r"\1=[REDACTED]", value)
    if isinstance(value, dict):
        return {str(k): _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def token_estimate(text: str) -> int:
    """Cheap deterministic token estimate for local comparisons."""
    return max(1, (len(text.strip()) + 3) // 4)


class TraceCollector:
    """Collect events in memory and optionally persist them as JSONL."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.trace_id = f"trace-{uuid4().hex[:12]}"
        self.run_id = f"run-{uuid4().hex[:12]}"
        self.events: list[TraceEvent] = []
        self.started = time.perf_counter()

    def record(
        self,
        *,
        agent: str,
        model: str,
        event: str,
        tool: str | None = None,
        input_text: str = "",
        output_text: str = "",
        latency: float = 0.0,
        status: str = "ok",
        retry_count: int = 0,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event_row = TraceEvent(
            trace_id=self.trace_id,
            run_id=self.run_id,
            agent=agent,
            model=model,
            tool=tool,
            event=event,
            input_tokens=token_estimate(input_text) if input_text else 0,
            output_tokens=token_estimate(output_text) if output_text else 0,
            latency=round(max(0.0, latency), 6),
            status=status,
            retry_count=retry_count,
            error=error,
            metadata=_redact(metadata or {}),
        )
        self.events.append(event_row)
        return event_row

    def flush(self) -> Path | None:
        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for event in self.events:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return self.path

    @property
    def elapsed(self) -> float:
        return round(time.perf_counter() - self.started, 6)
