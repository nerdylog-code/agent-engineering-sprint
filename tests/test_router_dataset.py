from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "router_dataset"


def test_router_dataset_has_separate_splits_and_expected_size() -> None:
    splits = [
        json.loads((DATASET / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("development", "calibration", "held_out_test")
    ]
    assert [len(items) for items in splits] == [120, 60, 60]
    assert len({item["id"] for items in splits for item in items}) == 240
    assert {item["expected_route"] for items in splits for item in items} == {
        "general_agent",
        "tool_agent",
        "rag_agent",
    }
    assert {item["language"] for items in splits for item in items} >= {"en", "pt-BR", "mixed"}
    assert any(len(item["input"]) > 4096 for items in splits for item in items)
    assert all(
        item["split"] in {"development", "calibration", "held_out_test"}
        for items in splits
        for item in items
    )


def test_held_out_cases_are_not_marked_for_threshold_fitting() -> None:
    held_out = json.loads((DATASET / "held_out_test.json").read_text(encoding="utf-8"))
    assert all(item["split"] == "held_out_test" for item in held_out)
    assert all(item["threshold_fit"] is False for item in held_out)
