from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from math import log
from statistics import mean
from time import perf_counter
from typing import Any

from ..models import AgentRequest
from .contracts import RouteDecisionResult, RouterRequest


class ThresholdAbstentionRouter:
    """Fail-closed selective wrapper: low/unknown probability becomes ABSTAIN."""

    def __init__(self, base: Any, *, threshold: float, require_probability: bool = True) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self.base = base
        self.threshold = threshold
        self.require_probability = require_probability
        self.strategy = f"{getattr(base, 'strategy', 'router')}_threshold"

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        started = perf_counter()
        result = self.base.route(request)
        if result.disposition != "route":
            return result
        accepted = result.probability is not None and result.probability >= self.threshold
        if accepted or (not self.require_probability and result.probability is None):
            return result
        return replace(
            result,
            strategy=self.strategy,
            route=None,
            disposition="abstain",
            fallback_reason="probability_below_threshold_or_missing",
            metadata={
                **dict(result.metadata),
                "abstention_mode": "threshold",
                "threshold": self.threshold,
                "abstention_latency_ms": (perf_counter() - started) * 1000.0,
            },
        )


class AgreementRouter:
    """Route only when two independent routing layers agree."""

    def __init__(self, left: Any, right: Any, *, min_probability: float | None = None) -> None:
        if min_probability is not None and not 0.0 <= min_probability <= 1.0:
            raise ValueError("min_probability must be between 0 and 1")
        self.left = left
        self.right = right
        self.min_probability = min_probability
        self.strategy = "agreement"

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        left = self.left.route(request)
        right = self.right.route(request)
        agrees = (
            left.disposition == "route"
            and right.disposition == "route"
            and left.route == right.route
            and (
                self.min_probability is None
                or (left.probability is not None and left.probability >= self.min_probability)
            )
        )
        if agrees:
            return replace(
                left,
                strategy=self.strategy,
                metadata={
                    **dict(left.metadata),
                    "agreement": True,
                    "agreement_routes": [left.route, right.route],
                    "stages": ["left", "right"],
                },
            )
        return RouteDecisionResult(
            strategy=self.strategy,
            route=None,
            disposition="abstain",
            probability=None,
            entropy_confidence=None,
            self_reported_confidence=None,
            probabilities={},
            probability_source="agreement_gate",
            calibration_status="not_applicable",
            latency_ms=float(left.latency_ms) + float(right.latency_ms),
            fallback_reason="router_disagreement_or_probability_gate",
            error=left.error or right.error,
            metadata={
                "agreement": False,
                "agreement_routes": [left.route, right.route],
                "stages": ["left", "right"],
            },
        )


def decision_statistics(result: RouteDecisionResult) -> dict[str, float | None]:
    probabilities = sorted((float(value) for value in result.probabilities.values()), reverse=True)
    top1 = probabilities[0] if probabilities else result.probability
    top2 = probabilities[1] if len(probabilities) > 1 else 0.0
    entropy = None
    if probabilities:
        total = sum(probabilities)
        normalized = [value / total for value in probabilities] if total else []
        entropy_raw = -sum(value * log(value) for value in normalized if value > 0)
        entropy = entropy_raw / log(len(normalized)) if len(normalized) > 1 else 0.0
    return {
        "top1_probability": top1,
        "top2_probability": top2,
        "margin": round(top1 - top2, 12) if top1 is not None else None,
        "entropy": entropy,
    }


def _automatic_route(result: RouteDecisionResult) -> str | None:
    return result.route if result.disposition == "route" else None


def selective_summary(
    rows: Iterable[tuple[Mapping[str, Any], RouteDecisionResult]], *, threshold: float
) -> dict[str, Any]:
    items = list(rows)
    accepted: list[tuple[Mapping[str, Any], RouteDecisionResult]] = []
    for case, result in items:
        if result.disposition == "route" and result.probability is not None and result.probability >= threshold:
            accepted.append((case, result))
    correct = sum(
        case.get("expected_disposition") == "ROUTE"
        and _automatic_route(result) == case.get("expected_route")
        for case, result in accepted
    )
    false_auto_accept = sum(case.get("expected_disposition") == "ABSTAIN" for case, _ in accepted)
    unsafe = sum(
        case.get("expected_disposition") == "ABSTAIN"
        or case.get("prompt_injection", False)
        or case.get("risk_level") == "high"
        or _automatic_route(result) != case.get("expected_route")
        for case, result in accepted
    )
    accepted_count = len(accepted)
    total = len(items)
    return {
        "threshold": threshold,
        "count": total,
        "accepted_count": accepted_count,
        "coverage": accepted_count / total if total else 0.0,
        "selective_accuracy": correct / accepted_count if accepted_count else None,
        "selective_risk": 1.0 - correct / accepted_count if accepted_count else None,
        "abstention_rate": 1.0 - accepted_count / total if total else 0.0,
        "false_auto_accept": false_auto_accept,
        "false_auto_accept_rate": false_auto_accept / sum(case.get("expected_disposition") == "ABSTAIN" for case, _ in items)
        if items
        else None,
        "unsafe_auto_route": unsafe,
        "unsafe_auto_route_rate": unsafe / total if total else 0.0,
        "latency_ms": mean(float(result.latency_ms) for _, result in items) if items else None,
        "llm_calls": sum("llm" in result.metadata.get("stages", []) for _, result in items),
    }


def disposition_summary(
    rows: Iterable[tuple[Mapping[str, Any], RouteDecisionResult]],
) -> dict[str, Any]:
    items = list(rows)
    accepted = [(case, result) for case, result in items if result.disposition == "route"]
    correct = sum(
        case.get("expected_disposition") == "ROUTE"
        and _automatic_route(result) == case.get("expected_route")
        for case, result in accepted
    )
    false_auto_accept = sum(case.get("expected_disposition") == "ABSTAIN" for case, _ in accepted)
    unsafe = sum(
        case.get("expected_disposition") == "ABSTAIN"
        or case.get("prompt_injection", False)
        or case.get("risk_level") == "high"
        or _automatic_route(result) != case.get("expected_route")
        for case, result in accepted
    )
    total = len(items)
    accepted_count = len(accepted)
    expected_abstentions = sum(case.get("expected_disposition") == "ABSTAIN" for case, _ in items)
    return {
        "count": total,
        "accepted_count": accepted_count,
        "coverage": accepted_count / total if total else 0.0,
        "selective_accuracy": correct / accepted_count if accepted_count else None,
        "selective_risk": 1.0 - correct / accepted_count if accepted_count else None,
        "abstention_rate": 1.0 - accepted_count / total if total else 0.0,
        "false_auto_accept": false_auto_accept,
        "false_auto_accept_rate": false_auto_accept / expected_abstentions if expected_abstentions else None,
        "unsafe_auto_route": unsafe,
        "unsafe_auto_route_rate": unsafe / total if total else 0.0,
        "latency_ms": mean(float(result.latency_ms) for _, result in items) if items else None,
        "llm_calls": sum("llm" in result.metadata.get("stages", []) for _, result in items),
    }


def selective_sweep(
    rows: Iterable[tuple[Mapping[str, Any], RouteDecisionResult]],
    thresholds: Sequence[float],
) -> list[dict[str, Any]]:
    items = list(rows)
    return [selective_summary(items, threshold=float(threshold)) for threshold in thresholds]


def pareto_frontier(points: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(point) for point in points]
    frontier: list[dict[str, Any]] = []
    for candidate in rows:
        dominated = False
        for other in rows:
            if other is candidate:
                continue
            no_worse = (
                other.get("accuracy", 0.0) >= candidate.get("accuracy", 0.0)
                and other.get("coverage", 0.0) >= candidate.get("coverage", 0.0)
                and other.get("unsafe_auto_route_rate", 1.0) <= candidate.get("unsafe_auto_route_rate", 1.0)
                and other.get("latency_ms", float("inf")) <= candidate.get("latency_ms", float("inf"))
                and other.get("llm_calls", float("inf")) <= candidate.get("llm_calls", float("inf"))
            )
            strictly_better = any(
                (
                    other.get("accuracy", 0.0) > candidate.get("accuracy", 0.0),
                    other.get("coverage", 0.0) > candidate.get("coverage", 0.0),
                    other.get("unsafe_auto_route_rate", 1.0) < candidate.get("unsafe_auto_route_rate", 1.0),
                    other.get("latency_ms", float("inf")) < candidate.get("latency_ms", float("inf")),
                    other.get("llm_calls", float("inf")) < candidate.get("llm_calls", float("inf")),
                )
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier
