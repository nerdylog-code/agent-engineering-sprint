import tempfile
import unittest
from pathlib import Path

from production_rag.dataset import build_synthetic_corpus
from production_rag.ingest import ingest_documents
from production_rag.models import Document
from production_rag.retrieval import HybridRetriever
from production_rag.storage import SQLiteCorpusStore


class RagStorageTests(unittest.TestCase):
    def test_corpus_survives_store_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.db"
            documents = build_synthetic_corpus(5)
            chunks = ingest_documents(documents)
            SQLiteCorpusStore(path).replace(documents, chunks)
            reopened = SQLiteCorpusStore(path)
            self.assertEqual(reopened.counts(), {"documents": 5, "chunks": 5})
            loaded = reopened.load_chunks()
            self.assertEqual(loaded[0].document_id, "doc-000")
            self.assertEqual(loaded[-1].document_id, "doc-004")

    def test_retrieval_enforces_tenant_and_principal_filters(self):
        documents = [
            Document("alpha", "alpha", "shared architecture evidence", {"tenant_id": "alpha"}),
            Document("beta", "beta", "shared architecture evidence", {"tenant_id": "beta"}),
            Document(
                "restricted",
                "restricted",
                "shared private evidence",
                {"tenant_id": "alpha", "allowed_principals": "alice"},
            ),
        ]
        retriever = HybridRetriever(ingest_documents(documents))
        alpha = retriever.search("shared architecture", tenant_id="alpha")
        beta = retriever.search("shared architecture", tenant_id="beta")
        restricted = retriever.search("shared private", tenant_id="alpha", principal="bob")
        allowed = retriever.search("shared private", tenant_id="alpha", principal="alice")
        self.assertEqual({hit.chunk.document_id for hit in alpha}, {"alpha"})
        self.assertEqual({hit.chunk.document_id for hit in beta}, {"beta"})
        self.assertNotIn("restricted", {hit.chunk.document_id for hit in restricted})
        self.assertEqual(allowed[0].chunk.document_id, "restricted")


if __name__ == "__main__":
    unittest.main()