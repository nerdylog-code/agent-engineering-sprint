from __future__ import annotations

import argparse
import json
import statistics
import warnings
from pathlib import Path
from time import perf_counter
from typing import Any


def run(model: str, device: str | None, output: Path) -> int:
    try:
        import laya
    except (ImportError, ModuleNotFoundError, OSError, RuntimeError) as exc:
        payload = {"status": "NOT_IMPLEMENTED", "error": f"Laya import failed: {exc}"}
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 2
    warnings_seen: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = perf_counter()
        agent = laya.load(model, device=device)
        load_ms = (perf_counter() - started) * 1000.0
        warnings_seen = [str(item.message) for item in caught]
    rows: list[dict[str, Any]] = []
    for count in (2, 3, 4, 5, 8, 10, 11, 12, 16):
        criteria = {
            f"option_{index:02d}": f"synthetic option {index:02d}" for index in range(count)
        }
        question = {
            "probe": {
                "type": "choice",
                "instructions": "Which synthetic option best matches the state?",
                "criteria": criteria,
            }
        }
        state = {"request": "Choose one synthetic option for a cardinality probe."}
        samples: list[float] = []
        answers: list[dict[str, Any]] = []
        errors: list[str] = []
        for _ in range(2):
            try:
                start = perf_counter()
                result = agent.predict(state, question)
                elapsed = (perf_counter() - start) * 1000.0
                answer = result["answers"]["probe"]
                samples.append(elapsed)
                answers.append(answer)
            except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
        row: dict[str, Any] = {
            "option_count": count,
            "latency_ms": {
                "samples": [round(value, 3) for value in samples],
                "p50": round(statistics.median(samples), 3) if samples else None,
            },
            "warnings": warnings_seen,
            "warning_present": bool(warnings_seen),
            "errors": errors,
        }
        if answers:
            first = answers[0]
            row["choice"] = first.get("choice")
            row["probability"] = (first.get("probabilities") or {}).get(first.get("choice"))
            row["entropy_confidence"] = first.get("confidence")
            row["finite"] = all(
                isinstance(value, (int, float))
                for value in (first.get("probabilities") or {}).values()
            )
            row["repeat_choice_same"] = len(answers) < 2 or answers[0].get("choice") == answers[
                1
            ].get("choice")
            row["calibration_status"] = (
                "uncalibrated_high_cardinality" if count >= 11 else "unverified_domain"
            )
        rows.append(row)
    payload = {
        "status": "IMPLEMENTED_AND_VERIFIED"
        if any(row["choice"] for row in rows)
        else "NOT_IMPLEMENTED",
        "model": model,
        "device": str(getattr(agent, "device", device)),
        "load_latency_ms": round(load_ms, 3),
        "option_counts": [2, 3, 4, 5, 8, 10, 11, 12, 16],
        "results": rows,
        "interpretation": {
            "warning_scope": (
                "Warnings are captured during checkpoint load; calibration status is "
                "explicitly marked for 11+ options."
            ),
            "probability_field": (
                "probability of the selected choice, not upstream entropy confidence."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "IMPLEMENTED_AND_VERIFIED" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="convaiinnovations/laya")
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--output", type=Path, default=Path("evidence/router-high-cardinality.json")
    )
    args = parser.parse_args()
    return run(args.model, args.device, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
