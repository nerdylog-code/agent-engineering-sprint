from __future__ import annotations

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.hybrid_router import HybridRouter
from agent_lab.decision.laya_router import LayaRouter
from agent_lab.decision.llm_router import LLMRouter, UnavailableLLMProvider
from agent_lab.decision.rules_router import RulesRouter


class Explodes:
    def __call__(self, *args, **kwargs):
        raise RuntimeError("checkpoint unavailable")


def test_laya_provider_failure_is_explicit() -> None:
    result = LayaRouter(predictor=Explodes()).route(RouterRequest("route", "ambiguous request"))
    assert result.disposition == "error"
    assert result.route is None
    assert "checkpoint unavailable" in (result.error or "")


def test_hybrid_falls_back_to_rules_when_laya_and_llm_are_unavailable() -> None:
    result = HybridRouter(
        RulesRouter(),
        LayaRouter(predictor=Explodes()),
        LLMRouter(provider=UnavailableLLMProvider("provider unavailable")),
        laya_probability_threshold=0.9,
    ).route(RouterRequest("route", "please explain this general request"))
    assert result.fallback is True
    assert result.route == "general_agent"
    assert "unavailable" in (result.fallback_reason or "")


def test_empty_input_abstains_without_provider_calls() -> None:
    result = HybridRouter(
        RulesRouter(), LayaRouter(predictor=Explodes()), LLMRouter(provider=Explodes())
    ).route(RouterRequest("route", ""))
    assert result.disposition == "abstain"
    assert result.route is None
