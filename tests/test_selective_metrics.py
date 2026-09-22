from __future__ import annotations

from agent_lab.decision.contracts import RouteDecisionResult
from agent_lab.decision.selective import (
    decision_statistics,
    disposition_summary,
    pareto_frontier,
    selective_summary,
)


def _result(route: str, probability: float, probabilities: dict[str, float]) -> RouteDecisionResult:
    return RouteDecisionResult(
        strategy="test",
        route=route,
        disposition="route",
        probability=probability,
        entropy_confidence=0.5,
        self_reported_confidence=None,
        probabilities=probabilities,
        probability_source="laya_choice_probability",
        calibration_status="test",
        latency_ms=2.0,
    )


def test_selective_summary_reports_coverage_risk_and_safety() -> None:
    rows = [
        ({"expected_disposition": "ROUTE", "expected_route": "general_agent", "risk_level": "low"}, _result("general_agent", 0.95, {"general_agent": 0.95, "tool_agent": 0.03, "rag_agent": 0.02})),
        ({"expected_disposition": "ROUTE", "expected_route": "tool_agent", "risk_level": "low"}, _result("general_agent", 0.70, {"general_agent": 0.70, "tool_agent": 0.20, "rag_agent": 0.10})),
        ({"expected_disposition": "ABSTAIN", "expected_route": None, "risk_level": "high", "prompt_injection": True}, _result("general_agent", 0.60, {"general_agent": 0.60, "tool_agent": 0.20, "rag_agent": 0.20})),
    ]
    summary = selective_summary(rows, threshold=0.90)
    assert summary["coverage"] == 1 / 3
    assert summary["selective_accuracy"] == 1.0
    assert summary["false_auto_accept"] == 0
    assert summary["unsafe_auto_route_rate"] == 0.0

    unsafe = selective_summary(rows, threshold=0.50)
    assert unsafe["false_auto_accept"] == 1
    assert unsafe["unsafe_auto_route_rate"] > 0.0


def test_decision_statistics_exposes_margin_and_entropy() -> None:
    stats = decision_statistics(_result("general_agent", 0.70, {"general_agent": 0.70, "tool_agent": 0.20, "rag_agent": 0.10}))
    assert stats["top1_probability"] == 0.70
    assert stats["top2_probability"] == 0.20
    assert stats["margin"] == 0.50
    assert 0.0 <= stats["entropy"] <= 1.0


def test_pareto_frontier_removes_dominated_policy() -> None:
    points = [
        {"policy": "dominated", "accuracy": 0.8, "coverage": 0.8, "unsafe_auto_route_rate": 0.2, "latency_ms": 20, "llm_calls": 10},
        {"policy": "safe", "accuracy": 0.8, "coverage": 0.7, "unsafe_auto_route_rate": 0.0, "latency_ms": 20, "llm_calls": 10},
        {"policy": "fast", "accuracy": 0.9, "coverage": 0.8, "unsafe_auto_route_rate": 0.1, "latency_ms": 10, "llm_calls": 5},
    ]
    frontier = pareto_frontier(points)
    assert {row["policy"] for row in frontier} == {"safe", "fast"}


def test_disposition_summary_handles_non_probabilistic_routes() -> None:
    rows = [
        ({"expected_disposition": "ROUTE", "expected_route": "general_agent", "risk_level": "low"}, _result("general_agent", 0.9, {"general_agent": 1.0})),
        ({"expected_disposition": "ABSTAIN", "expected_route": None, "risk_level": "high"}, _result("general_agent", 0.9, {"general_agent": 1.0})),
    ]
    summary = disposition_summary(rows)
    assert summary["coverage"] == 1.0
    assert summary["false_auto_accept"] == 1
    assert summary["unsafe_auto_route_rate"] == 0.5
