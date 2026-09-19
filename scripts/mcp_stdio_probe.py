"""Generate auditable evidence for the local MCP stdio JSON-RPC subset."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "calculator", "arguments": {"expression": "7 * 6"}}},
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    process = subprocess.run(
        [sys.executable, str(root / "scripts" / "mcp_stdio_server.py")],
        cwd=root,
        input="\n".join(json.dumps(message) for message in messages) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    rows = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
    tool_payload = json.loads(rows[-1]["result"]["content"][0]["text"]) if rows else {}
    payload = {
        "status": "pass" if process.returncode == 0 and tool_payload.get("output", {}).get("result") == 42.0 else "fail",
        "transport": "stdio-json-rpc",
        "methods_verified": ["initialize", "notifications/initialized", "tools/list", "tools/call"],
        "response_ids": [row.get("id") for row in rows],
        "tools": [tool["name"] for tool in rows[1]["result"]["tools"]] if len(rows) > 1 else [],
        "calculator_result": tool_payload.get("output", {}).get("result"),
        "stderr": process.stderr,
    }
    output = root / "evidence" / "provider" / "mcp-stdio-protocol.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
