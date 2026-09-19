"""Production RAG Lab public API."""

from .dataset import build_golden_dataset, build_synthetic_corpus
from .evaluator import evaluate_modes, evaluate_retrieval
from .retrieval import HybridRetriever

__all__ = [
    "HybridRetriever",
    "build_golden_dataset",
    "build_synthetic_corpus",
    "evaluate_modes",
    "evaluate_retrieval",
]
