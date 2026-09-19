import time
import unittest

from agent_lab.models import ToolResult
from agent_lab.tools import ToolRegistry, ToolSpec


class ToolTimeoutTests(unittest.TestCase):
    def test_hanging_tool_returns_bounded_error(self):
        registry = ToolRegistry()

        def hang(_: dict[str, object]) -> ToolResult:
            time.sleep(0.25)
            return ToolResult(name="hang", ok=True)

        registry.register(ToolSpec("hang_tool", hang, "test hanging handler"))
        started = time.perf_counter()
        result = registry.call("hang_tool", {}, timeout_seconds=0.02)
        elapsed = time.perf_counter() - started
        self.assertFalse(result.ok)
        self.assertIn("timed out", result.error or "")
        self.assertLess(elapsed, 0.15)

    def test_invalid_timeout_is_blocked(self):
        registry = ToolRegistry()
        registry.register(ToolSpec("quick_tool", lambda _: {"ok": True}, "test"))
        result = registry.call("quick_tool", {}, timeout_seconds=0)
        self.assertTrue(result.blocked)
        self.assertIn("positive", result.error or "")


if __name__ == "__main__":
    unittest.main()
