from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any

from ..models import AgentRequest
from .contracts import ROUTES, RouteDecisionResult, RouterRequest

QUESTION = {
    "route": {
        "type": "choice",
        "instructions": "Which existing agent should handle this request?",
        "criteria": {
            "general_agent": (
                "conversation, explanation, transformation, or general work "
                "without retrieval or tools"
            ),
            "tool_agent": "an explicit calculation, lookup, or allowlisted tool operation",
            "rag_agent": "retrieval of documents, citations, or grounded knowledge-base evidence",
        },
    }
}


def _request(request: RouterRequest | AgentRequest) -> RouterRequest:
    return (
        request if isinstance(request, RouterRequest) else RouterRequest.from_agent_request(request)
    )


class LayaRouter:
    """Optional upstream Laya adapter; no mock is used when the dependency is absent."""

    strategy = "laya"

    def __init__(
        self,
        *,
        predictor: Callable[..., Mapping[str, Any]] | None = None,
        device: str | None = None,
        preload: bool = False,
        model: str = "auto",
    ) -> None:
        self.predictor = predictor
        self.device = device
        self.preload = preload
        self.model = model
        self._router: Any | None = None

    def _load(self) -> Any:
        if self._router is not None:
            return self._router
        try:
            import laya
        except (ImportError, ModuleNotFoundError, OSError, RuntimeError) as exc:
            raise RuntimeError(f"Laya dependency unavailable: {exc}") from exc
        if not hasattr(laya, "Router"):
            raise RuntimeError("installed laya package does not expose Router")
        router = laya.Router(device=self.device, max_loaded=2, preload=False)
        if self.preload:
            router.preload(["english", "multilingual"])
        self._router = router
        return router

    def warmup(self) -> float:
        """Load configured checkpoints before timed routing calls."""
        if self.predictor is not None:
            return 0.0
        started = perf_counter()
        self._load()
        return (perf_counter() - started) * 1000.0

    @staticmethod
    def _language_model(language: str | None) -> str | None:
        if language is None:
            return None
        value = language.lower()
        if value in {"en", "english"}:
            return "english"
        if value in {"pt", "pt-br", "mixed", "multilingual"}:
            return "multilingual"
        return "multilingual"

    def _predict(self, request: RouterRequest, state: dict[str, str]) -> Mapping[str, Any]:
        if self.predictor is not None:
            return self.predictor(state, QUESTION)
        router = self._load()
        kwargs: dict[str, Any] = {}
        selected_model = self._language_model(request.language)
        if self.model != "auto":
            selected_model = self.model
        if selected_model is not None:
            kwargs["model"] = selected_model
        return router.predict(state, QUESTION, **kwargs)

    def _result_from_answer(
        self,
        answer: Mapping[str, Any],
        *,
        latency_ms: float,
        model: str | None,
        option_count: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RouteDecisionResult:
        if answer.get("type") != "choice":
            raise ValueError("Laya route answer is not a choice")
        route = answer.get("choice")
        probabilities = {
            str(key): float(value) for key, value in (answer.get("probabilities") or {}).items()
        }
        if route not in ROUTES:
            raise ValueError(f"Laya returned unknown route: {route!r}")
        if route not in probabilities:
            raise ValueError("Laya choice is missing its selected probability")
        count = option_count or len(probabilities)
        calibration_status = "uncalibrated_high_cardinality" if count >= 11 else "unverified_domain"
        return RouteDecisionResult(
            strategy=self.strategy,
            route=str(route),
            disposition="route",
            probability=probabilities[str(route)],
            entropy_confidence=float(answer["confidence"]),
            self_reported_confidence=None,
            probabilities=probabilities,
            probability_source="laya_choice_probability",
            calibration_status=calibration_status,
            latency_ms=latency_ms,
            metadata={**dict(metadata or {}), "laya_model": model, "option_count": count},
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
                probability_source="laya_choice_probability",
                calibration_status="not_applicable",
                latency_ms=0.0,
                metadata={"reason": "empty_input", "stages": ["laya"]},
            )
        try:
            payload = self._predict(
                request,
                {"objective": request.objective, "request": request.user_input},
            )
            answer = payload["answers"]["route"]
            routing = payload.get("routing", {})
            result = self._result_from_answer(
                answer,
                latency_ms=(perf_counter() - started) * 1000.0,
                model=payload.get("model") or routing.get("model"),
                metadata={
                    "routing": routing,
                    "input_tokens": payload.get("usage", {}).get("input_tokens"),
                    "output_tokens": payload.get("usage", {}).get("output_tokens"),
                    "actual_device": str(
                        getattr(
                            getattr(self._router, "_agents", {}).get(routing.get("model")),
                            "device",
                            None,
                        )
                    ),
                    "language": request.language,
                    "stages": ["laya"],
                },
            )
            return result
        except (IndexError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="error",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="laya_choice_probability",
                calibration_status="unknown",
                latency_ms=(perf_counter() - started) * 1000.0,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"stages": ["laya"]},
            )
