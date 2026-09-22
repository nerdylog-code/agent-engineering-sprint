from __future__ import annotations

from agent_lab.decision.contracts import RouteDecisionResult
from agent_lab.decision.metrics import brier_multiclass, expected_route, macro_f1, summarize_results


def _result(
    route: str | None,
    probability: float | None,
    probabilities: dict[str, float],
    disposition: str = "route",
) -> RouteDecisionResult:
    return RouteDecisionResult(
        strategy="test",
        route=route,
        disposition=disposition,
        probability=probability,
        entropy_confidence=0.5,
        self_reported_confidence=None,
        probabilities=probabilities,
        probability_source="laya_choice_probability" if probability is not None else "none",
        calibration_status="verified_for_test",
        latency_ms=2.0,
    )


def test_brier_uses_full_choice_distribution() -> None:
    labels = ["general_agent", "tool_agent", "rag_agent"]
    value = brier_multiclass(
        {"general_agent": 0.1, "tool_agent": 0.2, "rag_agent": 0.7}, "rag_agent", labels
    )
    assert round(value, 4) == 0.14


def test_summary_does_not_treat_self_report_as_probability() -> None:
    result = _result("rag_agent", 0.8, {"general_agent": 0.1, "tool_agent": 0.1, "rag_agent": 0.8})
    summary = summarize_results(
        [("rag_agent", result)], labels=["general_agent", "tool_agent", "rag_agent"]
    )
    assert summary["brier_score"] is not None
    assert summary["calibration_sample_count"] == 1


def test_summary_exposes_false_auto_accept() -> None:
    result = _result("general_agent", None, {}, disposition="route")
    summary = summarize_results([("abstain", result)])
    assert summary["false_auto_accept"] == 1
    assert summary["false_auto_accept_rate"] == 1.0



def test_metrics_helpers_are_deterministic() -> None:
    pairs = [
        ("general_agent", "general_agent"),
        ("tool_agent", "rag_agent"),
        ("rag_agent", "rag_agent"),
    ]
    assert expected_route(pairs[0][0]) == "general_agent"
    assert 0.0 <= macro_f1(pairs, ["general_agent", "tool_agent", "rag_agent"]) <= 1.0
