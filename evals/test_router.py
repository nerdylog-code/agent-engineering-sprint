import unittest

from agent_lab.router import route_request


class RouterEvaluation(unittest.TestCase):
    def test_golden_route_cases(self):
        cases = [
            ("retrieve evidence", "cite the document", "rag_agent"),
            ("calculate budget", "calcule 12 + 5", "tool_agent"),
            ("explain architecture", "give a concise overview", "general_agent"),
        ]
        for objective, user_input, expected in cases:
            with self.subTest(objective=objective):
                self.assertEqual(route_request(objective, user_input).route, expected)


if __name__ == "__main__":
    unittest.main()
