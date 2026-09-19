"""Local concurrency and failure-injection evidence for the service boundaries."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Self
from urllib.error import HTTPError

import httpx

from agent_lab.api import create_app
from agent_lab.providers import (
    CircuitBreaker,
    OpenAICompatibleProvider,
    ProviderError,
    RetryPolicy,
)
from agent_lab.tools import ToolRegistry, ToolSpec
from production_rag.storage import SQLiteCorpusStore


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * p) - 1))]


async def http_load(concurrency: int) -> dict[str, object]:
    app = create_app(rate_limit_per_window=concurrency + 10)
    transport = httpx.ASGITransport(app=app)
    latencies: list[float] = []
    statuses: list[int] = []

    async def request(index: int) -> None:
        started = time.perf_counter()
        async with httpx.AsyncClient(transport=transport, base_url="http://local") as client:
            response = await client.post("/v1/rag/query", json={"query": f"fact-{index % 50} evidence", "top_k": 5})
        latencies.append((time.perf_counter() - started) * 1000)
        statuses.append(response.status_code)

    started = time.perf_counter()
    await asyncio.gather(*(request(index) for index in range(concurrency)))
    duration = time.perf_counter() - started
    success = sum(status == 200 for status in statuses)
    return {
        "requests": concurrency,
        "successes": success,
        "success_rate": success / concurrency,
        "throughput_requests_per_second": concurrency / duration,
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": percentile(latencies, 0.95),
        "status_counts": {str(status): statuses.count(status) for status in sorted(set(statuses))},
    }


class _Response:
    def __init__(self, raw: str, status: int = 200) -> None:
        self.raw = raw.encode("utf-8")
        self.status = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.raw


def _opener_timeout(_: Any, timeout: float) -> _Response:
    raise TimeoutError(f"timeout after {timeout}")


def _opener_http(status: int):
    def opener(request: Any, timeout: float) -> _Response:
        raise HTTPError(str(request.full_url), status, "injected", {}, None)

    return opener


def _opener_malformed(_: Any, timeout: float) -> _Response:
    return _Response("{malformed", 200)


def _opener_healthy(_: Any, timeout: float) -> _Response:
    return _Response(
        json.dumps(
            {
                "id": "recovered",
                "model": "chaos-model",
                "choices": [{"message": {"role": "assistant", "content": "recovered"}, "finish_reason": "stop"}],
            }
        )
    )


def provider_case(name: str, opener: Any) -> dict[str, object]:
    provider = OpenAICompatibleProvider(
        base_url="http://provider.invalid/v1",
        model="chaos-model",
        opener=opener,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
    )
    started = time.perf_counter()
    try:
        provider.chat([{"role": "user", "content": "ping"}])
        result: dict[str, object] = {"status": "unexpected_success"}
    except ProviderError as exc:
        result = {"status": "expected_failure", "error_type": type(exc).__name__, "error": str(exc)}
    result.update({"case": name, "latency_ms": (time.perf_counter() - started) * 1000})
    return result


def chaos_cases() -> dict[str, object]:
    timeout = provider_case("provider_timeout", _opener_timeout)
    rate_limited = provider_case("provider_429", _opener_http(429))
    server_error = provider_case("provider_500", _opener_http(500))
    malformed = provider_case("malformed_json", _opener_malformed)

    registry = ToolRegistry()

    def hang(_: dict[str, Any]) -> str:
        time.sleep(0.2)
        return "late"

    registry.register(ToolSpec("hang_tool", hang, "injected hanging tool"))
    started = time.perf_counter()
    tool_result = registry.call("hang_tool", {}, timeout_seconds=0.02)
    tool_case = {
        "case": "hanging_tool",
        "status": "expected_failure" if not tool_result.ok else "unexpected_success",
        "error": tool_result.error,
        "latency_ms": (time.perf_counter() - started) * 1000,
    }

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "chaos.sqlite3"
        store = SQLiteCorpusStore(database, timeout_seconds=0.05)
        locker = sqlite3.connect(database)
        locker.execute("BEGIN IMMEDIATE")
        try:
            try:
                store.replace([], [])
                lock_status = "unexpected_success"
            except sqlite3.OperationalError as exc:
                lock_status = f"expected_failure: {exc}"
        finally:
            locker.rollback()
            locker.close()
        store.replace([], [])
        recovered = store.counts()
    sqlite_case = {"case": "sqlite_lock", "status": lock_status, "recovered_counts": recovered}

    breaker = CircuitBreaker(failure_threshold=1, reset_after_seconds=0)
    failing = OpenAICompatibleProvider(
        base_url="http://provider.invalid/v1",
        model="chaos-model",
        opener=_opener_http(500),
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0),
        circuit_breaker=breaker,
    )
    try:
        failing.chat([{"role": "user", "content": "fail"}])
    except ProviderError:
        pass
    failing._opener = _opener_healthy
    recovery = failing.chat([{"role": "user", "content": "recover"}])
    recovery_case = {"case": "provider_recovery", "status": "recovered" if recovery.content == "recovered" else "failed"}
    return {
        "provider_timeout": timeout,
        "provider_429": rate_limited,
        "provider_500": server_error,
        "malformed_json": malformed,
        "hanging_tool": tool_case,
        "sqlite_lock": sqlite_case,
        "provider_recovery": recovery_case,
    }


async def async_main(args: argparse.Namespace) -> dict[str, object]:
    load = await http_load(args.concurrency)
    failures = chaos_cases()
    return {"status": "pass", "load": load, "chaos": failures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("evidence/benchmarks/chaos-load.json"))
    args = parser.parse_args(argv)
    if not 1 <= args.concurrency <= 500:
        raise SystemExit("--concurrency must be between 1 and 500")
    payload = asyncio.run(async_main(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
