from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "router_safety_dataset"
ROUTES = {"general_agent", "tool_agent", "rag_agent"}


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split in ("development", "calibration", "held_out_test"):
        rows.extend(json.loads((DATASET / f"{split}.json").read_text(encoding="utf-8")))
    return rows


def test_safety_dataset_is_independent_and_balanced() -> None:
    rows = _rows()
    assert len(rows) == 180
    assert Counter(row["split"] for row in rows) == {
        "development": 90,
        "calibration": 45,
        "held_out_test": 45,
    }
    assert len({row["id"] for row in rows}) == 180
    assert len({row["category"] for row in rows}) >= 18
    assert sum(row["expected_disposition"] == "ABSTAIN" for row in rows) >= 60
    assert sum(row["prompt_injection"] for row in rows) >= 10
    assert sum(row["language"] == "pt-BR" for row in rows) >= 30
    assert any(len(str(row["input"])) > 4096 for row in rows)


def test_safety_labels_are_explicit_and_held_out_is_not_for_fitting() -> None:
    rows = _rows()
    for row in rows:
        assert row["expected_disposition"] in {"ROUTE", "ABSTAIN"}
        assert row["expected_route"] in ROUTES or row["expected_route"] is None
        assert row["threshold_fit"] is (row["split"] != "held_out_test")
        if row["expected_disposition"] == "ABSTAIN":
            assert row["expected_route"] is None
