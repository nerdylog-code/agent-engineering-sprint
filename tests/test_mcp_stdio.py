import json
import os
import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path

from agent_lab.mcp_server import MCPServer


class MCPStdioProtocolTests(unittest.TestCase):
    def test_in_process_handler_covers_protocol_errors_and_notification(self):
        server = MCPServer()
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 1, "method": "ping"})["result"], {})
        error = server.handle({"jsonrpc": "2.0", "id": 2, "method": "unknown"})
        self.assertEqual(error["error"]["code"], -32601)
        output = StringIO()
        server.serve(StringIO("not-json\n"), output)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], -32700)

    def test_real_stdio_initialize_list_and_call(self):
        root = Path(__file__).resolve().parents[1]
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "calculator", "arguments": {"expression": "7 * 6"}},
            },
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
        self.assertEqual(process.returncode, 0, process.stderr)
        rows = [json.loads(line) for line in process.stdout.splitlines() if line.strip()]
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertEqual(rows[0]["result"]["capabilities"]["tools"]["listChanged"], False)
        self.assertEqual({tool["name"] for tool in rows[1]["result"]["tools"]}, {"calculator", "lookup_faq"})
        content = json.loads(rows[2]["result"]["content"][0]["text"])
        self.assertEqual(content["output"]["result"], 42.0)
        self.assertFalse(rows[2]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
