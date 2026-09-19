"""Optional OpenTelemetry SDK bridge with an always-testable in-memory record."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpanRecord:
    name: str
    attributes: dict[str, Any]
    status: str
    duration_seconds: float


class Telemetry:
    """Use the SDK when installed; retain deterministic records as a fallback."""

    def __init__(self, *, console: bool = False) -> None:
        self.records: list[SpanRecord] = []
        self._tracer = None
        self._exporter = None
        try:
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

            provider = TracerProvider()
            self._exporter = InMemorySpanExporter()
            provider.add_span_processor(SimpleSpanProcessor(self._exporter))
            if console:
                from opentelemetry.sdk.trace.export import ConsoleSpanExporter

                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
            self._tracer = provider.get_tracer("agent-engineering-sprint")
        except ImportError:
            self._tracer = None

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
        attrs = {key: value for key, value in (attributes or {}).items() if value is not None}
        started = time.perf_counter()
        status = "ok"
        if self._tracer is None:
            try:
                yield
            except Exception:
                status = "error"
                raise
            finally:
                self.records.append(SpanRecord(name, attrs, status, time.perf_counter() - started))
            return
        with self._tracer.start_as_current_span(name) as sdk_span:
            for key, value in attrs.items():
                sdk_span.set_attribute(key, str(value) if not isinstance(value, (bool, int, float)) else value)
            try:
                yield
            except Exception as exc:
                status = "error"
                sdk_span.record_exception(exc)
                raise
            finally:
                self.records.append(SpanRecord(name, attrs, status, time.perf_counter() - started))

    def finished_sdk_spans(self) -> list[Any]:
        return list(self._exporter.get_finished_spans()) if self._exporter is not None else []
