"""Command line entry point for the agent lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import AgentRequest
from .orchestrator import AgentOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the offline Agent Engineering Lab")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run one deterministic agent request")
    demo.add_argument("--json", action="store_true")
    demo.add_argument("--trace", type=Path, default=Path("evidence/traces/demo.jsonl"))
    demo.add_argument("--objective", default="validate CI/CD tool routing")
    demo.add_argument("--input", default="calcule 7 * 6")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        result = AgentOrchestrator(trace_path=args.trace).run(
            AgentRequest(objective=args.objective, user_input=args.input)
        )
        payload = result.to_dict()
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["response"]["answer"])
        return 0 if result.status == "completed" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
