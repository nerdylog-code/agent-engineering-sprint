import tempfile
import unittest
from pathlib import Path

from production_rag.dataset import build_synthetic_corpus
from production_rag.ingest import ingest_documents
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


if __name__ == "__main__":
    unittest.main()