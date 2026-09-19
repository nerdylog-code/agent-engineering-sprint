import unittest

from agent_lab.models import AgentRequest
from agent_lab.orchestrator import AgentOrchestrator


class StructuredOutputEvaluation(unittest.TestCase):
    def test_invalid_first_attempt_is_repaired_within_bound(self):
        result = AgentOrchestrator().run(
            AgentRequest("structured output check", "hello"), max_retries=2, invalid_attempts=1
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.retries, 1)
        self.assertIsNotNone(result.response)
        result.response.validate()


if __name__ == "__main__":
    unittest.main()
