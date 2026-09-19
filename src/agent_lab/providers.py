"""Production-oriented OpenAI-compatible provider with bounded retries."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """Base error for provider failures."""


class ProviderTimeout(ProviderError):
    """Provider did not answer within the configured timeout."""


class ProviderCircuitOpen(ProviderError):
    """Calls are temporarily blocked after repeated provider failures."""


class ProviderResponseError(ProviderError):
    """Provider returned a malformed or unusable response."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    backoff_seconds: float = 0.15

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_after_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self, now: float | None = None) -> bool:
        if self.opened_at is None:
            return True
        current = time.monotonic() if now is None else now
        if current - self.opened_at >= self.reset_after_seconds:
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self, now: float | None = None) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic() if now is None else now

    def snapshot(self) -> dict[str, Any]:
        return {"failures": self.failures, "open": self.opened_at is not None}


@dataclass(frozen=True)
class ProviderToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ProviderResponse:
    provider_request_id: str | None
    model: str
    content: str
    finish_reason: str | None
    tool_calls: tuple[ProviderToolCall, ...] = ()
    usage: dict[str, int] = field(default_factory=dict)
    latency_seconds: float = 0.0

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class OpenAICompatibleProvider:
    """Small stdlib-only client for llama.cpp, vLLM, Ollama-compatible gateways, etc."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 45.0,
        retry_policy: RetryPolicy | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        opener: Any = urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._opener = opener
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http:// or https://")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> ProviderResponse:
        if not self.circuit_breaker.allow():
            raise ProviderCircuitOpen("provider circuit is open")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        last_error: ProviderError | None = None
        for attempt in range(self.retry_policy.max_attempts):
            started = time.perf_counter()
            try:
                request = Request(self.chat_url, data=body, headers=headers, method="POST")
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8", "replace")
                    status = getattr(response, "status", 200)
                if status >= 400:
                    raise ProviderError(f"provider HTTP {status}")
                result = self._parse(raw, time.perf_counter() - started)
                self.circuit_breaker.record_success()
                return result
            except HTTPError as exc:
                last_error = ProviderError(f"provider HTTP {exc.code}")
                retryable = exc.code == 429 or exc.code >= 500
            except (TimeoutError, URLError) as exc:
                last_error = ProviderTimeout(str(exc))
                retryable = True
            except ProviderError as exc:
                last_error = exc
                retryable = True
            if not retryable or attempt + 1 >= self.retry_policy.max_attempts:
                break
            self.circuit_breaker.record_failure()
            time.sleep(self.retry_policy.backoff_seconds * (attempt + 1))
        self.circuit_breaker.record_failure()
        raise last_error or ProviderError("provider call failed")

    def _parse(self, raw: str, latency: float) -> ProviderResponse:
        try:
            payload = json.loads(raw)
            choice = payload["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderResponseError(f"invalid provider response: {exc}") from exc
        calls: list[ProviderToolCall] = []
        for row in message.get("tool_calls", []) or []:
            try:
                function = row["function"]
                args = function.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                if not isinstance(args, dict):
                    raise TypeError("tool arguments must be an object")
                calls.append(ProviderToolCall(str(row.get("id", "")), str(function["name"]), args))
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderResponseError(f"invalid tool call: {exc}") from exc
        usage = payload.get("usage", {}) or {}
        normalized_usage = {
            key: int(value) for key, value in usage.items() if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
        }
        return ProviderResponse(
            provider_request_id=payload.get("id"),
            model=str(payload.get("model", self.model)),
            content=str(message.get("content") or ""),
            finish_reason=choice.get("finish_reason"),
            tool_calls=tuple(calls),
            usage=normalized_usage,
            latency_seconds=round(latency, 6),
        )

    def health(self) -> dict[str, Any]:
        """Return a redacted provider health snapshot without leaking the API key."""
        return {
            "base_url": self.base_url,
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "circuit": self.circuit_breaker.snapshot(),
            "checked_at": datetime.now(UTC).isoformat(),
        }
