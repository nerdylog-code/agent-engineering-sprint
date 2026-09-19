import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent_lab.api import create_app
from agent_lab.auth import JWTAuthenticator


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app())

    def test_health_and_readiness_are_operational(self):
        health = self.client.get("/healthz")
        ready = self.client.get("/readyz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["rag_documents"], 100)
        self.assertTrue(health.headers["x-request-id"])

    def test_agent_endpoint_returns_structured_result(self):
        response = self.client.post(
            "/v1/agent/runs",
            json={"objective": "calculate", "user_input": "calcule 7 * 6"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"]["status"], "completed")
        self.assertEqual(payload["result"]["tool_result"]["output"]["result"], 42.0)

    def test_rag_endpoint_returns_citations(self):
        response = self.client.post(
            "/v1/rag/query",
            json={"query": "What is fact-003 about ci-cd pipeline-gates?", "top_k": 3},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("doc-003", response.json()["citations"])

    def test_optional_api_token_and_metrics(self):
        client = TestClient(create_app(api_token="secret"))
        denied = client.post("/v1/agent/runs", json={"objective": "x", "user_input": "hello"})
        self.assertEqual(denied.status_code, 401)
        allowed = client.post(
            "/v1/agent/runs",
            headers={"Authorization": "Bearer secret"},
            json={"objective": "x", "user_input": "hello"},
        )
        self.assertEqual(allowed.status_code, 200)
        metrics = client.get("/metrics")
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("agent_http_requests_total", metrics.text)

    def test_api_can_boot_from_persistent_rag_store(self):
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(rag_store_path=str(Path(directory) / "rag.db")))
            ready = client.get("/readyz")
            self.assertTrue(ready.json()["rag_persistence"])
            self.assertEqual(ready.json()["rag_documents"], 100)

    def test_authenticated_rate_limit_returns_retry_after(self):
        client = TestClient(create_app(api_token="secret", rate_limit_per_window=1))
        headers = {"Authorization": "Bearer secret"}
        first = client.post("/v1/agent/runs", headers=headers, json={"objective": "x", "user_input": "hello"})
        second = client.post("/v1/agent/runs", headers=headers, json={"objective": "x", "user_input": "hello"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("retry-after", second.headers)

    def test_jwt_derives_tenant_and_rejects_body_mismatch(self):
        secret = "jwt-secret-0123456789-0123456789"
        auth = JWTAuthenticator(secret=secret)
        client = TestClient(create_app(jwt_secret=secret, rate_limit_per_window=10))
        token = auth.issue(subject="alice", tenant_id="tenant-a", roles=["user"], scopes=["rag:read"])
        headers = {"Authorization": f"Bearer {token}"}
        derived = client.post(
            "/v1/rag/query",
            headers=headers,
            json={"query": "fact-003 evidence"},
        )
        mismatch = client.post(
            "/v1/rag/query",
            headers=headers,
            json={"query": "fact-003 evidence", "tenant_id": "tenant-b"},
        )
        self.assertEqual(derived.status_code, 200)
        self.assertEqual(mismatch.status_code, 403)

    def test_api_records_otel_spans(self):
        app = create_app()
        client = TestClient(app)
        client.get("/healthz")
        client.post("/v1/rag/query", json={"query": "fact-003 evidence"})
        client.post("/v1/agent/runs", json={"objective": "calculate", "user_input": "calcule 2 + 2"})
        names = {span.name for span in app.state.telemetry.records}
        self.assertIn("http.request", names)
        self.assertIn("agent.run", names)
        self.assertIn("router.route", names)
        self.assertIn("tool.call", names)
        self.assertIn("retrieval.search", names)

    def test_mcp_http_requires_jwt_scope(self):
        secret = "mcp-http-secret-0123456789-012345"
        auth = JWTAuthenticator(secret=secret)
        app = create_app(jwt_secret=secret, rate_limit_per_window=20)
        client = TestClient(app)
        allowed_token = auth.issue(subject="alice", tenant_id="tenant-a", scopes=["tools:calculator"])
        denied_token = auth.issue(subject="bob", tenant_id="tenant-a", scopes=[])
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "calculator", "arguments": {"expression": "7 * 6"}},
        }
        allowed = client.post("/mcp", headers={"Authorization": f"Bearer {allowed_token}"}, json=body)
        denied = client.post("/mcp", headers={"Authorization": f"Bearer {denied_token}"}, json=body)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["result"]["content"][0]["text"].find("42.0") >= 0, True)
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(app.state.mcp_audit[-1]["allowed"])
        self.assertIn("tool.call", {span.name for span in app.state.telemetry.records})

    def test_mcp_http_rejects_invalid_token_and_times_out(self):
        secret = "mcp-timeout-secret-0123456789-0123"
        auth = JWTAuthenticator(secret=secret)
        app = create_app(jwt_secret=secret)
        client = TestClient(app)
        body = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "calculator", "arguments": {"expression": "1 + 1"}},
        }
        invalid = client.post("/mcp", headers={"Authorization": "Bearer invalid"}, json=body)
        self.assertEqual(invalid.status_code, 401)
        token = auth.issue(subject="alice", tenant_id="tenant-a", scopes=["tools:calculator"])
        original = app.state.mcp_server.handle

        def slow(payload):
            time.sleep(0.1)
            return original(payload)

        app.state.mcp_server.handle = slow
        app.state.mcp_timeout_seconds = 0.01
        timeout = client.post("/mcp", headers={"Authorization": f"Bearer {token}"}, json=body)
        self.assertEqual(timeout.status_code, 504)
        self.assertEqual(app.state.mcp_audit[-1]["reason"], "timeout")

    def test_rbac_rejects_user_and_allows_admin(self):
        secret = "rbac-test-secret-0123456789-012345"
        auth = JWTAuthenticator(secret=secret)
        app = create_app(jwt_secret=secret)
        client = TestClient(app)
        user = auth.issue(subject="alice", tenant_id="tenant-a", roles=["user"])
        admin = auth.issue(subject="root", tenant_id="tenant-a", roles=["admin"])
        denied = client.get("/v1/admin/mcp-audit", headers={"Authorization": f"Bearer {user}"})
        allowed = client.get("/v1/admin/mcp-audit", headers={"Authorization": f"Bearer {admin}"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
