from __future__ import annotations

import re
from time import perf_counter

from ..models import AgentRequest
from ..router import route_request
from .contracts import RouteDecisionResult, RouterRequest

_ARITHMETIC_RE = re.compile(r"[0-9][0-9\s+*/().%^-]*[0-9)]")


def _request(request: RouterRequest | AgentRequest) -> RouterRequest:
    return (
        request if isinstance(request, RouterRequest) else RouterRequest.from_agent_request(request)
    )


class RulesRouter:
    """Adapter around the existing route_request baseline; route_request is untouched."""

    strategy = "rules"

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        request = _request(request)
        started = perf_counter()
        if not request.user_input.strip():
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="abstain",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="deterministic_rule",
                calibration_status="not_applicable",
                latency_ms=(perf_counter() - started) * 1000.0,
                metadata={"reason": "empty_input", "stages": ["rules"]},
            )
        try:
            decision = route_request(request.objective, request.user_input)
            return RouteDecisionResult(
                strategy=self.strategy,
                route=decision.route,
                disposition="route",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="deterministic_rule",
                calibration_status="not_applicable",
                latency_ms=(perf_counter() - started) * 1000.0,
                selected_tool=decision.selected_tool,
                metadata={"reason": decision.reason, "stages": ["rules"]},
            )
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="error",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="deterministic_rule",
                calibration_status="not_applicable",
                latency_ms=(perf_counter() - started) * 1000.0,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"stages": ["rules"]},
            )

    def is_obvious(self, request: RouterRequest | AgentRequest) -> bool:
        request = _request(request)
        text = f"{request.objective} {request.user_input}".lower()
        if not request.user_input.strip():
            return False
        if _ARITHMETIC_RE.search(text) or any(
            marker in text for marker in ("calculate", "calcule", "soma", "multiplique")
        ):
            return True
        return any(
            marker in text
            for marker in (
                "retrieve the document",
                "retrieve from the knowledge base",
                "cite the source",
                "use the knowledge base",
                "recupere da base de conhecimento",
                "cite as fontes",
            )
        )
