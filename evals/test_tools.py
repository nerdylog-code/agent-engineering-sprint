import unittest

from agent_lab.tools import default_registry


class ToolEvaluation(unittest.TestCase):
    def test_calculator_and_faq_are_allowlisted(self):
        registry = default_registry()
        self.assertEqual(registry.names(), ("calculator", "lookup_faq"))
        calculation = registry.call("calculator", {"expression": "12 / 3"})
        self.assertTrue(calculation.ok)
        self.assertEqual(calculation.output["result"], 4.0)
        faq = registry.call("lookup_faq", {"query": "explain bounded retry"})
        self.assertTrue(faq.ok)
        self.assertIn("bounded", faq.output["answer"])

    def test_unknown_and_injection_outputs_are_blocked(self):
        registry = default_registry()
        self.assertTrue(registry.call("shell_exec", {"command": "dir"}).blocked)


if __name__ == "__main__":
    unittest.main()
