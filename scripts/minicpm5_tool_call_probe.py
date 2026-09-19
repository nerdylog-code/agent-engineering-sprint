"""Direct MiniCPM5/OpenAI-compatible tool-call probe.

This script never fabricates a pass. It writes status=unavailable when the local
endpoint is down and status=fail when HTTP works but no real tool call occurs.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from agent_lab.models import AgentRequest
from agent_lab.provider_runner import ProviderAgentRunner
from agent_lab.providers import OpenAICompatibleProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("AGENT_PROVIDER_BASE_URL", "http://127.0.0.1:8082/v1"))
    parser.add_argument("--model", default=os.environ.get("AGENT_PROVIDER_MODEL", "MiniCPM5-2B-Q8"))
    parser.add_argument("--api-key", default=os.environ.get("AGENT_PROVIDER_API_KEY", "local-only"))
    parser.add_argument("--output", type=Path, default=Path("evidence/provider/minicpm5-tool-call.json"))
    args = parser.parse_args(argv)
    provider = OpenAICompatibleProvider(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        timeout_seconds=90,
    )
    result = ProviderAgentRunner(provider, trace_path=Path("evidence/traces/minicpm5-tool-call.jsonl")).run(
        AgentRequest("real local tool call validation", "Use the calculator tool to calculate 7 * 6."),
        require_tool=True,
    )
    payload = {
        "status": result.status,
        "base_url": args.base_url,
        "model": args.model,
        "result": result.to_dict(),
        "validated_claim": result.status == "completed" and bool(result.tool_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
