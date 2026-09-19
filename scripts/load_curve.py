"""Run the local ASGI load harness at several concurrency levels."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from chaos_load import http_load


async def run_curve(levels: list[int]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for level in levels:
        result = await http_load(level)
        result["concurrency"] = level
        result["error_rate"] = round(1.0 - float(result["success_rate"]), 6)
        rows.append(result)
    return {
        "status": "pass" if all(row["success_rate"] == 1.0 for row in rows) else "degraded",
        "methodology": "asyncio + httpx against local FastAPI ASGITransport; not distributed capacity",
        "levels": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", nargs="+", type=int, default=[1, 10, 25, 50, 100, 200])
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmarks/load-curve.json"))
    args = parser.parse_args(argv)
    if any(level <= 0 or level > 500 for level in args.levels):
        raise SystemExit("levels must be between 1 and 500")
    payload = asyncio.run(run_curve(args.levels))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] in {"pass", "degraded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
