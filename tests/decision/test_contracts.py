from __future__ import annotations

import pytest

from agent_lab.decision.contracts import RouteDecisionResult


def test_probability_and_confidence_are_separate_fields() -> None:
    result = RouteDecisionResult(
        strategy="laya",
        route="rag_agent",
        disposition="route",
        probability=0.9536,
        entropy_confidence=0.8280,
        self_reported_confidence=None,
        probabilities={"general_agent": 0.0146, "tool_agent": 0.0179, "rag_agent": 0.9536},
        probability_source="laya_choice_probability",
        calibration_status="unverified_domain",
        latency_ms=10.0,
    )
    payload = result.to_dict()
    assert payload["probability"] == 0.9536
    assert payload["entropy_confidence"] == 0.828
    assert payload["probability"] != payload["entropy_confidence"]


def test_invalid_route_probability_is_rejected() -> None:
    with pytest.raises(ValueError, match="probability"):
        RouteDecisionResult(
            strategy="bad",
            route="general_agent",
            disposition="route",
            probability=1.1,
            entropy_confidence=None,
            self_reported_confidence=None,
            probabilities={},
            probability_source="none",
            calibration_status="not_applicable",
            latency_ms=0.0,
        )
