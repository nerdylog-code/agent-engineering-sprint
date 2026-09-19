import unittest

from production_rag.adversarial import build_adversarial_corpus, build_adversarial_dataset


class AdversarialDatasetTests(unittest.TestCase):
    def test_dataset_keeps_answerable_and_abstention_cases(self):
        corpus = build_adversarial_corpus()
        questions = build_adversarial_dataset()
        self.assertEqual(len(corpus), 24)
        self.assertEqual(len(questions), 54)
        self.assertEqual(sum(row["expected_document"] is None for row in questions), 6)
        self.assertIn("multilingual", {str(row["category"]) for row in questions})
        self.assertIn("typo", {str(row["category"]) for row in questions})


if __name__ == "__main__":
    unittest.main()
