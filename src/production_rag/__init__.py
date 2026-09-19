"""Production RAG Lab public API."""

from .dataset import build_golden_dataset, build_synthetic_corpus
from .embeddings import FastEmbedBackend, HashEmbeddingBackend
from .evaluator import evaluate_modes, evaluate_retrieval
from .retrieval import HybridRetriever
from .storage import SQLiteCorpusStore

__all__ = [
    "FastEmbedBackend",
    "HashEmbeddingBackend",
    "HybridRetriever",
    "SQLiteCorpusStore",
    "build_golden_dataset",
    "build_synthetic_corpus",
    "evaluate_modes",
    "evaluate_retrieval",
]
