from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "router_dataset" / "held_out_test.json"
BENCHMARK = ROOT / "evidence" / "router-benchmark-heldout-final.json"


def expected(row: dict[str, Any]) -> str:
    return row["expected_route"] if row["expected_disposition"] == "route" else "abstain"


def correct(row: dict[str, Any], result: dict[str, Any]) -> bool:
    actual = result.get("route") if result.get("disposition") == "route" else "abstain"
    return actual == expected(row)


def main() -> int:
    dataset = {row["id"]: row for row in json.loads(DATASET.read_text(encoding="utf-8"))}
    results: dict[str, dict[str, Any]] = {}
    if BENCHMARK.exists():
        payload = json.loads(BENCHMARK.read_text(encoding="utf-8"))
        results = {
            name: {row["id"]: row["result"] for row in strategy["rows"]}
            for name, strategy in payload["strategies"].items()
        }
    cases: dict[str, list[dict[str, Any]]] = {
        "rules_correct_laya_wrong": [],
        "laya_correct_rules_wrong": [],
        "llm_correct_laya_wrong": [],
        "hybrid_correct": [],
        "all_wrong": [],
    }
    for case_id, row in dataset.items():
        flags = {
            name: correct(row, table[case_id])
            for name, table in results.items()
            if case_id in table
        }
        if "rules" in flags and "laya" in flags:
            if flags["rules"] and not flags["laya"]:
                cases["rules_correct_laya_wrong"].append(case_id)
            if flags["laya"] and not flags["rules"]:
                cases["laya_correct_rules_wrong"].append(case_id)
        if "llm" in flags and "laya" in flags and flags["llm"] and not flags["laya"]:
            cases["llm_correct_laya_wrong"].append(case_id)
        if flags.get("hybrid"):
            cases["hybrid_correct"].append(case_id)
        if flags and not any(flags.values()):
            cases["all_wrong"].append(case_id)

    def example(case_id: str) -> dict[str, Any]:
        row = dataset[case_id]
        raw_input = str(row["input"])
        return {
            "id": case_id,
            "input_preview": raw_input[:480] + ("…[truncated]" if len(raw_input) > 480 else ""),
            "input_chars": len(raw_input),
            "expected_route": row["expected_route"],
            "expected_disposition": row["expected_disposition"],
            "difficulty": row["difficulty"],
            "language": row["language"],
            "adversarial": row["adversarial"],
            "strategies": {
                name: results[name].get(case_id) for name in results if case_id in results[name]
            },
        }

    output = {name: [example(case_id) for case_id in ids[:8]] for name, ids in cases.items()}
    output["counts"] = {name: len(ids) for name, ids in cases.items()}
    json_path = ROOT / "evidence" / "router-error-analysis.json"
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["# Routing Error Analysis", "", "Generated from held-out evidence only.", ""]
    for name, ids in cases.items():
        lines.extend([f"## {name}", "", f"Count: **{len(ids)}**", ""])
        for case_id in ids[:8]:
            row = dataset[case_id]
            lines.append(f"### `{case_id}` — {row['language']} / {row['difficulty']}")
            lines.append(f"- Expected: `{expected(row)}`")
            raw_input = str(row["input"])
            preview = raw_input[:480] + ("…[truncated]" if len(raw_input) > 480 else "")
            lines.append(f"- Input ({len(raw_input)} chars): {preview!r}")
            for strategy, strategy_results in results.items():
                result = strategy_results.get(case_id)
                if result:
                    lines.append(
                        f"- {strategy}: `{result.get('route')}` / "
                        f"{result.get('disposition')} probability={result.get('probability')} "
                        f"entropy_confidence={result.get('entropy_confidence')} "
                        f"self_reported={result.get('self_reported_confidence')} "
                        f"fallback={result.get('fallback')}"
                    )
            lines.append("")
    (ROOT / "docs" / "ROUTING_ERROR_ANALYSIS.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(output["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
