import unittest

from agent_lab.models import AgentRequest
from agent_lab.orchestrator import AgentOrchestrator


class AgentQualityEvaluation(unittest.TestCase):
    def test_task_success_and_tool_selection_accuracy(self):
        cases = [
            ("calculate", "calcule 2 + 2", "calculator"),
            ("find evidence", "retrieve a document citation", None),
            ("explain", "hello", None),
            ("faq", "use a tool to explain retry", "lookup_faq"),
        ]
        results = [AgentOrchestrator().run(AgentRequest(objective, text)) for objective, text, _ in cases]
        self.assertTrue(all(result.status == "completed" for result in results))
        matches = sum(
            result.route.selected_tool == expected
            for result, (_objective, _text, expected) in zip(results, cases)
        )
        self.assertEqual(matches / len(cases), 1.0)

    def test_retry_rate_is_measurable(self):
        result = AgentOrchestrator().run(
            AgentRequest("quality", "hello"), max_retries=2, invalid_attempts=1
        )
        self.assertEqual(result.retries, 1)
        self.assertLessEqual(result.retries, 2)


if __name__ == "__main__":
    unittest.main()
