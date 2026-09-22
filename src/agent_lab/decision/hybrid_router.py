from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from ..models import AgentRequest
from .contracts import RouteDecisionResult, RouterRequest
from .laya_router import LayaRouter
from .llm_router import LLMRouter
from .rules_router import RulesRouter


def _request(request: RouterRequest | AgentRequest) -> RouterRequest:
    return (
        request if isinstance(request, RouterRequest) else RouterRequest.from_agent_request(request)
    )


class HybridRouter:
    strategy = "hybrid"

    def __init__(
        self,
        rules: RulesRouter,
        laya: LayaRouter,
        llm: LLMRouter,
        *,
        laya_probability_threshold: float = 0.90,
    ) -> None:
        if not 0.0 <= laya_probability_threshold <= 1.0:
            raise ValueError("laya_probability_threshold must be between 0 and 1")
        self.rules = rules
        self.laya = laya
        self.llm = llm
        self.laya_probability_threshold = laya_probability_threshold

    def _with_hybrid(
        self,
        result: RouteDecisionResult,
        *,
        stages: list[str],
        fallback: bool | None = None,
        fallback_reason: str | None = None,
        **metadata: object,
    ) -> RouteDecisionResult:
        merged_metadata: dict[str, object] = {
            **dict(result.metadata),
            **metadata,
            "stages": stages,
        }
        return replace(
            result,
            strategy=self.strategy,
            fallback=result.fallback if fallback is None else fallback,
            fallback_reason=result.fallback_reason if fallback_reason is None else fallback_reason,
            metadata=merged_metadata,
        )

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        request = _request(request)
        started = perf_counter()
        if not request.user_input.strip():
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="abstain",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="hybrid_gate",
                calibration_status="not_applicable",
                latency_ms=0.0,
                metadata={"stages": []},
            )
        rules_result = self.rules.route(request)
        if self.rules.is_obvious(request):
            return self._with_hybrid(
                rules_result, stages=["rules"], gate_basis="obvious_deterministic_rule"
            )
        laya_result = self.laya.route(request)
        stages = ["laya"]
        if (
            laya_result.disposition == "route"
            and laya_result.probability is not None
            and laya_result.probability >= self.laya_probability_threshold
            and laya_result.calibration_status != "uncalibrated_high_cardinality"
        ):
            return self._with_hybrid(
                laya_result,
                stages=stages,
                gate_basis="laya_selected_probability",
                threshold=self.laya_probability_threshold,
            )
        llm_result = self.llm.route(request)
        stages.append("llm")
        if llm_result.disposition == "route":
            return self._with_hybrid(
                llm_result,
                stages=stages,
                gate_basis="llm_after_laya_low_or_unavailable",
                laya_probability=laya_result.probability,
                laya_error=laya_result.error,
            )
        if rules_result.disposition == "route":
            return self._with_hybrid(
                rules_result,
                stages=stages + ["rules_fallback"],
                fallback=True,
                fallback_reason="Laya did not pass probability gate and LLM was unavailable",
                latency_ms=(perf_counter() - started) * 1000.0,
            )
        return RouteDecisionResult(
            strategy=self.strategy,
            route=None,
            disposition="abstain",
            probability=None,
            entropy_confidence=None,
            self_reported_confidence=None,
            probabilities={},
            probability_source="hybrid_gate",
            calibration_status="unknown",
            latency_ms=(perf_counter() - started) * 1000.0,
            fallback=True,
            fallback_reason="all providers unavailable",
            error=llm_result.error or laya_result.error,
            metadata={"stages": stages},
        )
