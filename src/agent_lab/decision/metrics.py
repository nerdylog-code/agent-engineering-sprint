from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from statistics import mean

from .contracts import ROUTES, RouteDecisionResult


def expected_route(value: str) -> str:
    if value not in ROUTES:
        raise ValueError(f"unknown expected route: {value!r}")
    return value


def brier_multiclass(
    probabilities: Mapping[str, float], actual: str, labels: Sequence[str] = ROUTES
) -> float:
    return float(
        sum(
            (float(probabilities.get(label, 0.0)) - (1.0 if label == actual else 0.0)) ** 2
            for label in labels
        )
    )


def macro_f1(pairs: Iterable[tuple[str, str | None]], labels: Sequence[str] = ROUTES) -> float:
    rows = list(pairs)
    scores = []
    for label in labels:
        tp = sum(actual == label and expected == label for expected, actual in rows)
        fp = sum(actual == label and expected != label for expected, actual in rows)
        fn = sum(actual != label and expected == label for expected, actual in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(mean(scores)) if scores else 0.0


def _ece(samples: list[tuple[float, bool]], bins: int = 10) -> float | None:
    if not samples:
        return None
    total = len(samples)
    value = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        bucket = [
            (prob, correct)
            for prob, correct in samples
            if lower < prob <= upper or (index == 0 and prob == 0)
        ]
        if bucket:
            value += (
                len(bucket)
                / total
                * abs(
                    mean(prob for prob, _ in bucket) - mean(float(correct) for _, correct in bucket)
                )
            )
    return float(value)


def summarize_results(
    rows: Iterable[tuple[str, RouteDecisionResult]],
    *,
    labels: Sequence[str] = ROUTES,
) -> dict[str, object]:
    items = list(rows)
    pairs = [
        (expected, result.route if result.disposition == "route" else None)
        for expected, result in items
    ]
    correct = [expected == (actual or "abstain") for expected, actual in pairs]
    route_pairs = [(expected, actual) for expected, actual in pairs if expected in labels]
    probability_samples: list[tuple[float, bool]] = []
    brier_values: list[float] = []
    for expected, result in items:
        if (
            expected in labels
            and result.probability is not None
            and result.probabilities
            and result.probability_source == "laya_choice_probability"
        ):
            probability_samples.append((result.probability, result.route == expected))
            brier_values.append(brier_multiclass(result.probabilities, expected, labels))
    latencies = sorted(float(result.latency_ms) for _, result in items)

    def percentile(percent: float) -> float | None:
        if not latencies:
            return None
        position = (len(latencies) - 1) * percent
        lower = int(position)
        upper = min(lower + 1, len(latencies) - 1)
        fraction = position - lower
        return latencies[lower] + (latencies[upper] - latencies[lower]) * fraction

    llm_calls = sum(1 for _, result in items if "llm" in result.metadata.get("stages", []))
    input_tokens = sum(int(result.metadata.get("input_tokens", 0) or 0) for _, result in items)
    output_tokens = sum(int(result.metadata.get("output_tokens", 0) or 0) for _, result in items)
    return {
        "count": len(items),
        "accuracy": sum(correct) / len(correct) if correct else None,
        "macro_f1": macro_f1(route_pairs, labels),
        "abstention_rate": sum(actual is None for _, actual in pairs) / len(pairs)
        if pairs
        else None,
        "incorrect_automatic_routing": sum(
            actual is not None and actual != expected for expected, actual in pairs
        ),
        "fallback_rate": sum(result.fallback for _, result in items) / len(items)
        if items
        else None,
        "confusion_matrix": {
            expected: {
                actual_label: sum(
                    1
                    for exp, actual in pairs
                    if exp == expected and (actual or "abstain") == actual_label
                )
                for actual_label in [*labels, "abstain"]
            }
            for expected in [*labels, "abstain"]
        },
        "latency_ms": {
            "p50": percentile(0.50),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
            "mean": mean(latencies) if latencies else None,
        },
        "throughput_per_second": len(items) / (sum(latencies) / 1000.0)
        if latencies and sum(latencies) > 0
        else None,
        "brier_score": mean(brier_values) if brier_values else None,
        "ece": _ece(probability_samples),
        "calibration_sample_count": len(probability_samples),
        "llm_calls": llm_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
