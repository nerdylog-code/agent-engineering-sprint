"""Data contracts for the local agent harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class StructuredOutputError(ValueError):
    """Raised when an agent response violates the structured-output contract."""


@dataclass(frozen=True)
class AgentRequest:
    objective: str
    user_input: str
    request_id: str = field(default_factory=lambda: f"req-{uuid4().hex[:12]}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        if not self.user_input.strip():
            raise ValueError("user_input must not be empty")


@dataclass(frozen=True)
class RouteDecision:
    route: str
    selected_tool: str | None
    reason: str


@dataclass(frozen=True)
class StructuredOutput:
    answer: str
    route: str
    selected_tool: str | None
    confidence: float
    needs_approval: bool
    citations: tuple[str, ...] = ()

    def validate(self) -> StructuredOutput:
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise StructuredOutputError("answer must be a non-empty string")
        if not isinstance(self.route, str) or not self.route.strip():
            raise StructuredOutputError("route must be a non-empty string")
        if self.selected_tool is not None and not isinstance(self.selected_tool, str):
            raise StructuredOutputError("selected_tool must be a string or null")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise StructuredOutputError("confidence must be numeric")
        if not 0.0 <= self.confidence <= 1.0:
            raise StructuredOutputError("confidence must be between 0 and 1")
        if not isinstance(self.needs_approval, bool):
            raise StructuredOutputError("needs_approval must be boolean")
        if any(not isinstance(citation, str) or not citation.strip() for citation in self.citations):
            raise StructuredOutputError("citations must contain non-empty strings")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "route": self.route,
            "selected_tool": self.selected_tool,
            "confidence": self.confidence,
            "needs_approval": self.needs_approval,
            "citations": list(self.citations),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StructuredOutput:
        try:
            result = cls(
                answer=payload["answer"],
                route=payload["route"],
                selected_tool=payload.get("selected_tool"),
                confidence=payload["confidence"],
                needs_approval=payload["needs_approval"],
                citations=tuple(payload.get("citations", ())),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StructuredOutputError(f"invalid structured output: {exc}") from exc
        return result.validate()


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    output: Any = None
    error: str | None = None
    blocked: bool = False


@dataclass
class TraceEvent:
    trace_id: str
    run_id: str
    agent: str
    model: str
    tool: str | None
    event: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency: float = 0.0
    status: str = "ok"
    retry_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    trace_id: str
    status: str
    response: StructuredOutput | None
    route: RouteDecision
    tool_result: ToolResult | None
    retries: int
    latency: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "status": self.status,
            "response": self.response.to_dict() if self.response else None,
            "route": asdict(self.route),
            "tool_result": asdict(self.tool_result) if self.tool_result else None,
            "retries": self.retries,
            "latency": self.latency,
            "error": self.error,
        }
