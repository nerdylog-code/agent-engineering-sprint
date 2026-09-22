from __future__ import annotations

from agent_lab.decision.contracts import RouteDecisionResult
from agent_lab.decision.observability import decision_trace


def test_decision_trace_contains_required_fields_without_input_content() -> None:
    result = RouteDecisionResult(
        strategy="laya",
        route="rag_agent",
        disposition="route",
        probability=0.91,
        entropy_confidence=0.8,
        self_reported_confidence=None,
        probabilities={"general_agent": 0.02, "tool_agent": 0.07, "rag_agent": 0.91},
        probability_source="laya_choice_probability",
        calibration_status="unverified_domain",
        latency_ms=12.0,
    )
    trace = decision_trace(
        result, expected_route="rag_agent", correct=True, language="pt-BR", difficulty="hard"
    )
    assert trace["selected_probability"] == 0.91
    assert trace["calibration_bucket"] == "0.9-1.0"
    assert "input" not in trace
    assert trace["language"] == "pt-BR"
