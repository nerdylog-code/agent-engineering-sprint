"""CLI for the deterministic Production RAG Lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .dataset import build_golden_dataset, build_synthetic_corpus
from .evaluator import evaluate_modes
from .ingest import ingest_documents
from .retrieval import HybridRetriever


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    return build_golden_dataset(50)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the offline Production RAG Lab")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--json", action="store_true")
    evaluate.add_argument("--dataset", type=Path, default=Path("evals/golden_dataset.json"))
    evaluate.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "evaluate":
        documents = build_synthetic_corpus(100)
        chunks = ingest_documents(documents)
        retriever = HybridRetriever(chunks)
        result = {
            "documents": len(documents),
            "chunks": len(chunks),
            "dataset": str(args.dataset),
            "modes": evaluate_modes(retriever, _load_dataset(args.dataset)),
        }
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["modes"])
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
