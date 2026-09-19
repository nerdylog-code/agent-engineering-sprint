"""Minimal, dependency-free MCP stdio JSON-RPC server for allowlisted tools."""

from __future__ import annotations

import json
from typing import Any, TextIO

from .tools import ToolRegistry, default_registry

PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """Implement the stable initialize/tools/list/tools/call MCP subset."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or default_registry()
        self.initialized = False

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        request_id = message.get("id")
        if method == "notifications/initialized":
            self.initialized = True
            return None
        if method == "ping":
            return self._result(request_id, {})
        if method == "initialize":
            self.initialized = True
            return self._result(
                request_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "agent-engineering-sprint", "version": "0.1.0"},
                },
            )
        if method == "tools/list":
            return self._result(
                request_id,
                {
                    "tools": [
                        {
                            "name": schema["function"]["name"],
                            "description": schema["function"]["description"],
                            "inputSchema": schema["function"]["parameters"],
                        }
                        for schema in self.registry.schemas()
                    ]
                },
            )
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not isinstance(name, str):
                return self._error(request_id, -32602, "tools/call requires a string name")
            result = self.registry.call(name, arguments)
            payload = {"ok": result.ok, "output": result.output, "error": result.error}
            return self._result(
                request_id,
                {
                    "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                    "isError": not result.ok,
                },
            )
        return self._error(request_id, -32601, f"method not found: {method}")

    @staticmethod
    def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        for line in stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                response = self.handle(message)
                if response is not None:
                    stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    stdout.flush()
            except (json.JSONDecodeError, TypeError) as exc:
                stdout.write(json.dumps(self._error(None, -32700, str(exc))) + "\n")
                stdout.flush()
