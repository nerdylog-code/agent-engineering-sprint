from __future__ import annotations

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.rules_router import RulesRouter


def test_rules_router_wraps_the_existing_deterministic_router() -> None:
    result = RulesRouter().route(RouterRequest("route request", "calculate 7 * 6"))
    assert result.route == "tool_agent"
    assert result.selected_tool == "calculator"
    assert result.probability is None
    assert result.probability_source == "deterministic_rule"


def test_rules_router_abstains_on_empty_input_without_calling_existing_router() -> None:
    result = RulesRouter().route(RouterRequest("route request", " "))
    assert result.disposition == "abstain"
    assert result.route is None


def test_rules_router_marks_only_high_signal_cases_obvious() -> None:
    router = RulesRouter()
    assert router.is_obvious(RouterRequest("route", "calculate 4 + 4")) is True
    assert router.is_obvious(RouterRequest("route", "What is an agent tool?")) is False
