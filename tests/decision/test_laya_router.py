from __future__ import annotations

from agent_lab.decision.contracts import RouterRequest
from agent_lab.decision.laya_router import LayaRouter


class FakePredictor:
    def __call__(self, state, questions, **kwargs):
        assert "request" in state
        assert questions["route"]["type"] == "choice"
        return {
            "model": "fake-laya",
            "answers": {
                "route": {
                    "type": "choice",
                    "choice": "rag_agent",
                    "probabilities": {
                        "general_agent": 0.02,
                        "tool_agent": 0.03,
                        "rag_agent": 0.95,
                    },
                    "confidence": 0.82,
                }
            },
            "usage": {"input_tokens": 10, "output_tokens": 0},
        }


def test_laya_router_preserves_probability_and_entropy_confidence() -> None:
    result = LayaRouter(predictor=FakePredictor()).route(
        RouterRequest("route", "retrieve the policy and cite the source")
    )
    assert result.route == "rag_agent"
    assert result.probability == 0.95
    assert result.entropy_confidence == 0.82
    assert result.probability_source == "laya_choice_probability"
    assert result.calibration_status == "unverified_domain"


def test_laya_router_marks_high_cardinality_calibration_as_untrusted() -> None:
    router = LayaRouter(predictor=FakePredictor())
    result = router._result_from_answer(
        {
            "type": "choice",
            "choice": "rag_agent",
            "probabilities": {"rag_agent": 1 / 12, **{f"extra{i}": 1 / 12 for i in range(11)}},
            "confidence": 0.01,
        },
        latency_ms=1.0,
        model="fake",
        option_count=12,
    )
    assert result.calibration_status == "uncalibrated_high_cardinality"
