import unittest

from production_rag.dataset import build_golden_dataset, build_synthetic_corpus
from production_rag.evaluator import evaluate_modes
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever


class RagEvaluation(unittest.TestCase):
    def test_golden_dataset_is_50_questions_over_100_documents(self):
        dataset = build_golden_dataset(50)
        retriever = HybridRetriever(ingest_documents(build_synthetic_corpus(100)))
        metrics = evaluate_modes(retriever, dataset)
        self.assertEqual(len(dataset), 50)
        self.assertEqual(metrics["hybrid_reranker"]["questions"], 50)
        self.assertGreaterEqual(metrics["hybrid_reranker"]["recall_at_5"], 0.95)
        self.assertGreaterEqual(metrics["hybrid_reranker"]["mrr"], 0.9)


if __name__ == "__main__":
    unittest.main()
