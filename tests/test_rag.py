import unittest

from production_rag.dataset import build_synthetic_corpus
from production_rag.evaluator import evaluate_modes, evaluate_retrieval
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever


class ProductionRagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = build_synthetic_corpus(100)
        cls.retriever = HybridRetriever(ingest_documents(cls.documents))

    def test_ingestion_preserves_all_documents(self):
        self.assertEqual(len(self.documents), 100)
        self.assertEqual(len({chunk.document_id for chunk in self.retriever.chunks}), 100)

    def test_hybrid_reranker_finds_exact_fact(self):
        hits = self.retriever.search("fact-017 security least-privilege", top_k=3)
        self.assertEqual(hits[0].chunk.document_id, "doc-017")
        self.assertGreaterEqual(hits[0].keyword_score, 0.5)

    def test_answer_has_citations_and_groundedness(self):
        answer = self.retriever.answer("What is fact-003 about ci-cd pipeline-gates?")
        self.assertIn("doc-003", answer.citations)
        self.assertGreater(answer.groundedness, 0.5)
        self.assertGreater(answer.answer_relevance, 0.2)

    def test_answer_abstains_when_only_stopwords_match(self):
        answer = self.retriever.answer("What is the recipe for an unrelated object?")
        self.assertEqual(answer.citations, ())
        self.assertEqual(answer.groundedness, 0.0)

    def test_measured_hybrid_metrics(self):
        dataset = [
            {
                "question": f"What is fact-{i:03d} about the topic?",
                "expected_document": f"doc-{i:03d}",
                "expected_terms": [f"fact-{i:03d}"],
            }
            for i in range(20)
        ]
        result = evaluate_retrieval(self.retriever, dataset, mode="hybrid", rerank=True)
        self.assertEqual(result["questions"], 20)
        self.assertGreaterEqual(result["recall_at_5"], 0.95)
        self.assertGreaterEqual(result["mrr"], 0.9)

    def test_mode_comparison_returns_three_real_variants(self):
        dataset = [
            {
                "question": "What is fact-000 about observability tracing?",
                "expected_document": "doc-000",
                "expected_terms": ["fact-000", "observability"],
            }
        ]
        result = evaluate_modes(self.retriever, dataset)
        self.assertEqual(set(result), {"vector_only", "hybrid", "hybrid_reranker"})


if __name__ == "__main__":
    unittest.main()
