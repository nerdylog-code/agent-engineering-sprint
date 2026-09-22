from __future__ import annotations

from agent_lab.decision.authorization import authorize_action
from agent_lab.decision.contracts import RouteDecisionResult, RouterRequest
from agent_lab.decision.laya_router import LayaRouter
from agent_lab.decision.selective import AgreementRouter, ThresholdAbstentionRouter


class ExplicitPredictor:
    def __call__(self, state, questions):
        assert "ABSTAIN" in questions["route"]["criteria"]
        return {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "ABSTAIN",
                    "probabilities": {
                        "general_agent": 0.20,
                        "tool_agent": 0.10,
                        "rag_agent": 0.10,
                        "ABSTAIN": 0.60,
                    },
                    "confidence": 0.10,
                }
            }
        }


class LowProbabilityPredictor:
    def __call__(self, state, questions):
        return {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "general_agent",
                    "probabilities": {
                        "general_agent": 0.40,
                        "tool_agent": 0.35,
                        "rag_agent": 0.25,
                    },
                    "confidence": 0.01,
                }
            }
        }


class SafeRoute:
    strategy = "fake"

    def __init__(self, route: str = "general_agent") -> None:
        self.route_name = route
        self.calls = 0

    def route(self, request):
        self.calls += 1
        return RouteDecisionResult(
            strategy="fake",
            route=self.route_name,
            disposition="route",
            probability=0.9,
            entropy_confidence=0.5,
            self_reported_confidence=None,
            probabilities={self.route_name: 0.9},
            probability_source="test",
            calibration_status="test",
            latency_ms=1.0,
        )


def test_explicit_abstention_is_a_first_class_result() -> None:
    result = LayaRouter(predictor=ExplicitPredictor(), abstention_mode="explicit").route(
        RouterRequest("route safely", "unclear request")
    )
    assert result.disposition == "abstain"
    assert result.route is None
    assert result.probability == 0.60
    assert result.metadata["abstention_mode"] == "explicit"


def test_threshold_abstention_converts_low_probability_route() -> None:
    base = LayaRouter(predictor=LowProbabilityPredictor())
    result = ThresholdAbstentionRouter(base, threshold=0.50).route(
        RouterRequest("route safely", "unclear request")
    )
    assert result.disposition == "abstain"
    assert result.route is None
    assert result.metadata["abstention_mode"] == "threshold"


def test_agreement_router_abstains_when_routes_disagree() -> None:
    result = AgreementRouter(SafeRoute("general_agent"), SafeRoute("tool_agent")).route(
        RouterRequest("route safely", "unclear request")
    )
    assert result.disposition == "abstain"
    assert result.metadata["agreement"] is False


def test_routing_does_not_authorize_sensitive_action() -> None:
    decision = authorize_action("tool_agent", "refund", approved=False)
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.reason == "sensitive_action_requires_deterministic_approval"
