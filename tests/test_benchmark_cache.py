from __future__ import annotations

from agent_lab.decision.contracts import RouteDecisionResult, RouterRequest
from scripts.router_benchmark import MemoizingRouter


class Delegate:
    def __init__(self) -> None:
        self.calls = 0

    def route(self, request: RouterRequest) -> RouteDecisionResult:
        self.calls += 1
        return RouteDecisionResult(
            strategy="llm",
            route="general_agent",
            disposition="route",
            probability=None,
            entropy_confidence=None,
            self_reported_confidence=0.8,
            probabilities={},
            probability_source="self_reported_confidence",
            calibration_status="not_calibrated",
            latency_ms=5.0,
            metadata={"input_tokens": 10, "output_tokens": 2},
        )


def test_memoizing_router_reuses_threshold_sweep_result_without_charging_tokens() -> None:
    delegate = Delegate()
    router = MemoizingRouter(delegate)
    request = RouterRequest("objective", "hello", case_id="case-1")

    first = router.route(request)
    second = router.route(request)

    assert delegate.calls == 1
    assert first.route == second.route == "general_agent"
    assert second.metadata["cache_hit"] is True
    assert second.metadata["input_tokens"] == 0
    assert second.metadata["output_tokens"] == 0


def test_usage_comparison_reports_call_and_cost_savings() -> None:
    from scripts.router_benchmark import annotate_usage

    strategies = {
        "llm": {"summary": {"llm_calls": 10}, "cost": {"estimated_cost": 1.0}},
        "hybrid": {"summary": {"llm_calls": 4}, "cost": {"estimated_cost": 0.4}},
    }

    annotate_usage(strategies)

    assert strategies["hybrid"]["usage_vs_full_llm"] == {
        "llm_call_reduction": 6,
        "llm_call_reduction_rate": 0.6,
        "estimated_cost_savings": 0.6,
    }
