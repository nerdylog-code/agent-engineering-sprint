"""Run the local MCP endpoint over a self-signed HTTPS certificate."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import subprocess
import sys
import time
from http.client import HTTPSConnection
from pathlib import Path

from agent_lab.auth import JWTAuthenticator


def request(url_host: str, port: int, token: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    context = ssl._create_unverified_context()
    connection = HTTPSConnection(url_host, port, context=context, timeout=10)
    connection.request(
        "POST",
        "/mcp",
        body=json.dumps(body),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    response = connection.getresponse()
    payload = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--output", type=Path, default=Path("evidence/security/mcp-http-tls.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    tls_dir = root / "evidence" / "runtime" / "tls"
    tls_dir.mkdir(parents=True, exist_ok=True)
    cert = tls_dir / "localhost.crt"
    key = tls_dir / "localhost.key"
    if not cert.exists() or not key.exists():
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    secret = "mcp-tls-secret-0123456789-012345"
    environment = os.environ.copy()
    environment["AGENT_JWT_SECRET"] = secret
    environment["PYTHONPATH"] = str(root / "src")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_lab.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--ssl-keyfile",
            str(key),
            "--ssl-certfile",
            str(cert),
        ],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        auth = JWTAuthenticator(secret=secret)
        allowed = auth.issue(subject="alice", tenant_id="tenant-a", scopes=["tools:calculator"])
        denied = auth.issue(subject="bob", tenant_id="tenant-a", scopes=[])
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "calculator", "arguments": {"expression": "7 * 6"}},
        }
        last_error: Exception | None = None
        for _ in range(50):
            try:
                allowed_status, allowed_payload = request("127.0.0.1", args.port, allowed, body)
                denied_status, denied_payload = request("127.0.0.1", args.port, denied, body)
                break
            except (ConnectionError, OSError) as exc:
                last_error = exc
                time.sleep(0.1)
        else:
            raise RuntimeError("HTTPS server did not become ready") from last_error
        payload = {
            "status": "pass" if allowed_status == 200 and denied_status == 403 else "fail",
            "transport": "HTTPS with self-signed localhost certificate",
            "certificate": str(cert.relative_to(root)),
            "allowed_call": {"status_code": allowed_status, "response": allowed_payload},
            "denied_call": {"status_code": denied_status, "response": denied_payload},
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["status"] == "pass" else 1
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
