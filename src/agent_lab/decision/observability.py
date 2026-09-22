from __future__ import annotations

from typing import Any

from .contracts import RouteDecisionResult


def calibration_bucket(probability: float | None) -> str | None:
    if probability is None:
        return None
    lower = min(0.9, max(0.0, int(probability * 10) / 10))
    upper = min(1.0, lower + 0.1)
    return f"{lower:.1f}-{upper:.1f}"


def decision_trace(
    result: RouteDecisionResult,
    *,
    expected_route: str | None = None,
    correct: bool | None = None,
    language: str | None = None,
    difficulty: str | None = None,
) -> dict[str, Any]:
    """Return a redaction-free routing trace with no request content."""
    return {
        "trace_id": result.trace_id,
        "router_strategy": result.strategy,
        "decision_engine": result.strategy,
        "selected_route": result.route,
        "expected_route": expected_route,
        "correct": correct,
        "probability": result.probability,
        "selected_probability": result.probability,
        "entropy_confidence": result.entropy_confidence,
        "self_reported_confidence": result.self_reported_confidence,
        "probability_source": result.probability_source,
        "calibration_status": result.calibration_status,
        "calibration_bucket": calibration_bucket(result.probability),
        "scores": dict(result.probabilities),
        "latency_ms": result.latency_ms,
        "fallback": result.fallback,
        "fallback_reason": result.fallback_reason,
        "language": language,
        "difficulty": difficulty,
        "disposition": result.disposition,
        "error": result.error,
    }
