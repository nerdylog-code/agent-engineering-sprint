from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Literal, Protocol
from uuid import uuid4

from ..models import AgentRequest

ROUTES = ("general_agent", "tool_agent", "rag_agent")
ABSTAIN_OPTION = "ABSTAIN"
Disposition = Literal["route", "abstain", "error"]


@dataclass(frozen=True, slots=True)
class RouterRequest:
    """Evaluation request that permits empty input so abstention can be measured."""

    objective: str
    user_input: str
    language: str | None = None
    case_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_agent_request(cls, request: AgentRequest) -> RouterRequest:
        return cls(request.objective, request.user_input, metadata=request.metadata)


@dataclass(frozen=True, slots=True)
class RouteDecisionResult:
    """Comparable route output with probability provenance made explicit."""

    strategy: str
    route: str | None
    disposition: Disposition
    probability: float | None
    entropy_confidence: float | None
    self_reported_confidence: float | None
    probabilities: Mapping[str, float]
    probability_source: str
    calibration_status: str
    latency_ms: float
    selected_tool: str | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    error: str | None = None
    trace_id: str = field(default_factory=lambda: f"trace-{uuid4().hex[:12]}")
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.strategy.strip():
            raise ValueError("strategy must not be empty")
        if self.disposition not in ("route", "abstain", "error"):
            raise ValueError("invalid disposition")
        if self.disposition == "route" and self.route not in ROUTES:
            raise ValueError(f"route must be one of {ROUTES}")
        if self.disposition != "route" and self.route is not None:
            raise ValueError("abstain/error results cannot select a route")
        for name, value in (
            ("probability", self.probability),
            ("entropy_confidence", self.entropy_confidence),
            ("self_reported_confidence", self.self_reported_confidence),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                raise ValueError(f"{name} must be between 0 and 1")
        if not isfinite(float(self.latency_ms)) or float(self.latency_ms) < 0.0:
            raise ValueError("latency_ms must be finite and non-negative")
        for label, value in self.probabilities.items():
            if not isinstance(label, str) or not 0.0 <= float(value) <= 1.0:
                raise ValueError("probabilities must map strings to values between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "route": self.route,
            "disposition": self.disposition,
            "probability": self.probability,
            "entropy_confidence": self.entropy_confidence,
            "self_reported_confidence": self.self_reported_confidence,
            "probabilities": dict(self.probabilities),
            "probability_source": self.probability_source,
            "calibration_status": self.calibration_status,
            "latency_ms": self.latency_ms,
            "selected_tool": self.selected_tool,
            "fallback": self.fallback,
            "fallback_reason": self.fallback_reason,
            "error": self.error,
            "trace_id": self.trace_id,
            "metadata": dict(self.metadata),
        }


class Router(Protocol):
    strategy: str

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult: ...
