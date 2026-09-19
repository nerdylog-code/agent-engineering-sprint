"""Run the same local gates that CI runs, without hidden network dependencies."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_gate(name: str, args: list[str]) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    started = time.perf_counter()
    process = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return {
        "name": name,
        "command": args,
        "returncode": process.returncode,
        "duration_seconds": round(time.perf_counter() - started, 6),
        "stdout": process.stdout,
        "stderr": process.stderr,
        "status": "pass" if process.returncode == 0 else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local CI gates")
    parser.add_argument("--strict", action="store_true", help="return non-zero when any gate fails")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    gates = [
        ("compile", [sys.executable, "-m", "compileall", "-q", "src", "evals", "tests", "scripts"]),
        ("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests", "evals", "scripts"]),
        ("mypy", [sys.executable, "-m", "mypy", "src"]),
        ("bandit", [sys.executable, "-m", "bandit", "-q", "-r", "src", "-ll"]),
        ("unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("evals", [sys.executable, "-m", "unittest", "discover", "-s", "evals", "-v"]),
        ("mcp_protocol", [sys.executable, "scripts/mcp_stdio_probe.py"]),
        ("benchmark", [sys.executable, "scripts/benchmark.py", "--runs", "100"]),
        ("coverage", [sys.executable, "-m", "pytest", "--cov=src", "--cov-branch", "--cov-report=term-missing", "--cov-fail-under=80"]),
        ("dependency_audit", [sys.executable, "-m", "pip_audit", ".", "--format", "json"]),
        ("security", [sys.executable, "scripts/security_scan.py", "--json"]),
        ("rag_smoke", [sys.executable, "-m", "production_rag.cli", "evaluate", "--json"]),
    ]
    results = [run_gate(name, command) for name, command in gates]
    payload = {"status": "pass" if all(row["status"] == "pass" for row in results) else "fail", "gates": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for row in results:
            print(f"[{row['status'].upper()}] {row['name']} ({row['duration_seconds']}s)")
            if row["status"] == "fail":
                print(row["stdout"])
                print(row["stderr"])
    return 0 if payload["status"] == "pass" or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
