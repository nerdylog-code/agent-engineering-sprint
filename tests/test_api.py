import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from agent_lab.api import create_app


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


if __name__ == "__main__":
    unittest.main()
