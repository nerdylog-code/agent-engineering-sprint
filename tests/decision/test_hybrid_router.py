from __future__ import annotations

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.hybrid_router import HybridRouter
from agent_lab.decision.laya_router import LayaRouter
from agent_lab.decision.llm_router import LLMRouter
from agent_lab.decision.rules_router import RulesRouter


class NeverCalled:
    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("provider should not be called")


class LowLaya:
    def __call__(self, state, questions, **kwargs):
        return {
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "general_agent",
                    "probabilities": {"general_agent": 0.55, "tool_agent": 0.25, "rag_agent": 0.20},
                    "confidence": 0.10,
                }
            },
            "usage": {"input_tokens": 4, "output_tokens": 0},
        }


class GoodLLM:
    def route(self, request):
        return {"route": "rag_agent", "confidence": 0.9, "input_tokens": 4, "output_tokens": 3}


def test_hybrid_uses_obvious_rules_before_laya() -> None:
    laya = NeverCalled()
    result = HybridRouter(
        RulesRouter(), LayaRouter(predictor=laya), LLMRouter(provider=GoodLLM())
    ).route(RouterRequest("route", "calculate 2 + 2"))
    assert result.route == "tool_agent"
    assert result.metadata["stages"] == ["rules"]
    assert laya.calls == 0


def test_hybrid_escalates_low_probability_laya_to_llm() -> None:
    result = HybridRouter(
        RulesRouter(),
        LayaRouter(predictor=LowLaya()),
        LLMRouter(provider=GoodLLM()),
        laya_probability_threshold=0.8,
    ).route(RouterRequest("route", "ambiguous request"))
    assert result.route == "rag_agent"
    assert result.metadata["stages"] == ["laya", "llm"]
    assert result.probability is None
    assert result.self_reported_confidence == 0.9
