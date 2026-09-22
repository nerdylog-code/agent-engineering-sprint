from __future__ import annotations

import pytest

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.llm_router import LLMRouter, OllamaJSONProvider


class FakeLLM:
    def route(self, request):
        return {
            "route": "general_agent",
            "confidence": 0.84,
            "input_tokens": 12,
            "output_tokens": 8,
        }


class InvalidLLM:
    def route(self, request):
        return {"route": "made_up_agent", "confidence": 0.99}


def test_llm_confidence_is_self_reported_not_probability() -> None:
    result = LLMRouter(provider=FakeLLM()).route(RouterRequest("route", "say hello"))
    assert result.route == "general_agent"
    assert result.self_reported_confidence == 0.84
    assert result.probability is None
    assert result.probability_source == "self_reported_confidence"
    assert result.calibration_status == "not_a_probability"


def test_llm_invalid_route_is_fail_closed() -> None:
    result = LLMRouter(provider=InvalidLLM()).route(RouterRequest("route", "say hello"))
    assert result.route is None
    assert result.disposition == "error"
    assert result.error


def test_ollama_provider_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="http or https"):
        OllamaJSONProvider(base_url="file:///unsafe")
