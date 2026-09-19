"""Reproduce the five-minute portfolio demo without external services."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_lab.api import create_app
from agent_lab.auth import JWTAuthenticator


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    secret = "five-minute-demo-secret-0123456789"
    auth = JWTAuthenticator(secret=secret)
    app = create_app(jwt_secret=secret, rate_limit_per_window=50)
    client = TestClient(app)
    user = auth.issue(subject="alice", tenant_id="tenant-a", roles=["user"], scopes=["tools:calculator"])
    admin = auth.issue(subject="root", tenant_id="tenant-a", roles=["admin"], scopes=[])
    headers = {"Authorization": f"Bearer {user}"}
    body = {"query": "What is fact-003 about ci-cd pipeline-gates?", "top_k": 3}
    rag = client.post("/v1/rag/query", headers=headers, json=body)
    agent = client.post(
        "/v1/agent/runs",
        headers=headers,
        json={"objective": "calculate", "user_input": "calcule 7 * 6"},
    )
    cross_tenant = client.post(
        "/v1/rag/query", headers=headers, json={**body, "tenant_id": "tenant-b"}
    )
    role_denied = client.get("/v1/admin/mcp-audit", headers=headers)
    role_allowed = client.get("/v1/admin/mcp-audit", headers={"Authorization": f"Bearer {admin}"})
    mcp_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "calculator", "arguments": {"expression": "7 * 6"}},
    }
    mcp_allowed = client.post("/mcp", headers=headers, json=mcp_body)
    no_scope = auth.issue(subject="bob", tenant_id="tenant-a", roles=["user"], scopes=[])
    mcp_denied = client.post("/mcp", headers={"Authorization": f"Bearer {no_scope}"}, json=mcp_body)
    span_names = sorted({span.name for span in app.state.telemetry.records})
    payload = {
        "status": "pass",
        "steps": [
            {"name": "rag_tenant_a", "status_code": rag.status_code},
            {"name": "agent_run", "status_code": agent.status_code},
            {"name": "cross_tenant", "status_code": cross_tenant.status_code},
            {"name": "user_admin_route", "status_code": role_denied.status_code},
            {"name": "admin_route", "status_code": role_allowed.status_code},
            {"name": "mcp_scoped_tool", "status_code": mcp_allowed.status_code},
            {"name": "mcp_missing_scope", "status_code": mcp_denied.status_code},
        ],
        "otel_spans_seen": span_names,
        "expected": {"rag_tenant_a": 200, "agent_run": 200, "cross_tenant": 403, "user_admin_route": 403, "admin_route": 200, "mcp_scoped_tool": 200, "mcp_missing_scope": 403},
    }
    payload["status"] = "pass" if all(
        step["status_code"] == payload["expected"][step["name"]] for step in payload["steps"]
    ) else "fail"
    output = root / "evidence" / "demo" / "five-minute-demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
