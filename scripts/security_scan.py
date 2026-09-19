"""Small static security gate for the offline lab."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "src", ROOT / "tests", ROOT / "evals")
PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    "shell_escape": re.compile(r"(?i)os\.system\s*\(|shell\s*=\s*True"),
}


def scan() -> dict[str, object]:
    findings: list[dict[str, object]] = []
    files_scanned = 0
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            files_scanned += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in PATTERNS.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    findings.append({"rule": name, "file": str(path.relative_to(ROOT)), "line": line})
    return {"status": "pass" if not findings else "fail", "files_scanned": files_scanned, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = scan()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
