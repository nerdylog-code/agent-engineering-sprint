"""Generate a redacted local OpenTelemetry span inventory for a demo."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_lab.api import create_app


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app = create_app()
    client = TestClient(app)
    client.get("/healthz")
    client.post("/v1/rag/query", json={"query": "fact-003 evidence", "top_k": 3})
    client.post("/v1/agent/runs", json={"objective": "calculate", "user_input": "calcule 7 * 6"})
    payload = {
        "status": "pass",
        "span_count": len(app.state.telemetry.records),
        "spans": [
            {
                "name": record.name,
                "status": record.status,
                "attributes": record.attributes,
                "duration_seconds": round(record.duration_seconds, 8),
            }
            for record in app.state.telemetry.records
        ],
        "sdk_finished_spans": len(app.state.telemetry.finished_sdk_spans()),
        "redaction": "no prompts, tokens, API keys or document contents stored",
    }
    output = root / "evidence" / "traces" / "otel-spans-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
