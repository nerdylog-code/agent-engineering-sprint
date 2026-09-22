from __future__ import annotations

import re
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any

from ..models import AgentRequest
from .contracts import RouteDecisionResult, RouterRequest


@dataclass(frozen=True, slots=True)
class SafetyGateDecision:
    blocked: bool
    category: str | None = None
    reason: str | None = None


class SafetyPreGate:
    """Deterministic content gate; it never selects an agent or authorizes an action."""

    _injection = re.compile(
        r"ignore previous|system\s*:|<system>|always output|correct route is|for testing purposes classify|instruction.{0,80}output",
        re.IGNORECASE,
    )
    _unsafe = re.compile(
        r"delete (?:the )?production|send a refund|credential|external write|alter the fiscal|bypass approval",
        re.IGNORECASE,
    )

    def check(self, request: RouterRequest | AgentRequest) -> SafetyGateDecision:
        if not isinstance(request, RouterRequest):
            request = RouterRequest.from_agent_request(request)
        text = request.user_input.strip()
        lowered = text.lower()
        if not text:
            return SafetyGateDecision(True, "empty_input", "request has no content")
        if len(text) > 12000:
            return SafetyGateDecision(True, "very_long_input", "input exceeds safety context budget")
        if request.language and request.language.lower() == "unsupported":
            return SafetyGateDecision(True, "unsupported_language", "language is outside the measured policy")
        if self._injection.search(text):
            return SafetyGateDecision(True, "prompt_injection", "instruction-like content attempted to control routing")
        if self._unsafe.search(text):
            return SafetyGateDecision(True, "unsafe_request", "sensitive action requires deterministic approval")
        if lowered.endswith("...") or ("{route:" in lowered and "}" not in lowered):
            return SafetyGateDecision(True, "malformed_or_truncated", "request appears incomplete or malformed")
        if ("calculate" in lowered or "calcule" in lowered) and any(
            marker in lowered for marker in ("retrieve", "knowledge base", "policy", "cite", "summarize", "either agent")
        ):
            return SafetyGateDecision(True, "conflicting_intents", "request combines independent intents")
        if any(marker in lowered for marker in ("can you handle this", "do the needful", "move it there", "previous number")):
            return SafetyGateDecision(True, "insufficient_context", "request depends on missing context")
        return SafetyGateDecision(False)


class SafetyGatedRouter:
    """Apply the deterministic safety pre-gate before any probabilistic router."""

    def __init__(self, base: Any, *, gate: SafetyPreGate | None = None) -> None:
        self.base = base
        self.gate = gate or SafetyPreGate()
        self.strategy = f"{getattr(base, 'strategy', 'router')}_safety"

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        started = perf_counter()
        decision = self.gate.check(request)
        if decision.blocked:
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="abstain",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="deterministic_safety_gate",
                calibration_status="not_applicable",
                latency_ms=(perf_counter() - started) * 1000.0,
                fallback_reason=decision.reason,
                metadata={
                    "stages": ["safety_gate"],
                    "safety_category": decision.category,
                    "safety_gate": "blocked",
                },
            )
        result = self.base.route(request)
        return replace(
            result,
            strategy=self.strategy,
            metadata={**dict(result.metadata), "safety_gate": "passed", "stages": ["safety_gate", *dict(result.metadata).get("stages", [])]},
        )
