from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlparse

from ..models import AgentRequest
from .contracts import ROUTES, RouteDecisionResult, RouterRequest


class LLMProvider(Protocol):
    def route(self, request: RouterRequest) -> Mapping[str, Any]: ...


class UnavailableLLMProvider:
    def __init__(self, reason: str = "LLM provider not configured") -> None:
        self.reason = reason

    def route(self, request: RouterRequest) -> Mapping[str, Any]:
        raise RuntimeError(self.reason)


class OllamaJSONProvider:
    """Configurable local Ollama provider with JSON-schema-constrained output."""

    def __init__(
        self, *, model: str | None = None, base_url: str | None = None, timeout_s: float = 30.0
    ) -> None:
        self.model = model or os.getenv("ROUTER_LLM_MODEL", "qwen2.5:7b")
        raw_base_url = base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
        parsed_base_url = urlparse(raw_base_url)
        if parsed_base_url.scheme not in {"http", "https"}:
            raise ValueError("OLLAMA_BASE_URL must use http or https")
        self.base_url = raw_base_url.rstrip("/")
        self.timeout_s = timeout_s

    def route(self, request: RouterRequest) -> Mapping[str, Any]:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "route": {"type": "string", "enum": list(ROUTES)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["route", "confidence"],
        }
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Route the request to exactly one existing agent. Return only JSON with "
                        "route and confidence. Confidence is self-reported, not a "
                        "calibrated probability. "
                        "general_agent handles general work; tool_agent handles "
                        "explicit tools/calculation; "
                        "rag_agent handles retrieval/citations/knowledge-base evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Objective: {request.objective}\nRequest: {request.user_input}",
                },
            ],
        }
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        http_request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(  # nosec B310
            http_request, timeout=self.timeout_s
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload.get("message", {}).get("content", "")
        parsed = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed, dict):
            raise TypeError("Ollama returned non-object structured output")
        return {
            **parsed,
            "input_tokens": payload.get("prompt_eval_count", 0),
            "output_tokens": payload.get("eval_count", 0),
            "model": payload.get("model", self.model),
        }


def provider_from_environment() -> LLMProvider:
    name = os.getenv("ROUTER_LLM_PROVIDER", "unavailable").lower()
    if name == "ollama":
        return OllamaJSONProvider()
    return UnavailableLLMProvider("set ROUTER_LLM_PROVIDER=ollama to enable the local LLM baseline")


def _request(request: RouterRequest | AgentRequest) -> RouterRequest:
    return (
        request if isinstance(request, RouterRequest) else RouterRequest.from_agent_request(request)
    )


class LLMRouter:
    strategy = "llm"

    def __init__(self, *, provider: LLMProvider | None = None) -> None:
        self.provider = provider or provider_from_environment()

    def route(self, request: RouterRequest | AgentRequest) -> RouteDecisionResult:
        request = _request(request)
        started = perf_counter()
        if not request.user_input.strip():
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="abstain",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="self_reported_confidence",
                calibration_status="not_applicable",
                latency_ms=0.0,
                metadata={"stages": ["llm"]},
            )
        try:
            payload = self.provider.route(request)
            route = payload.get("route")
            confidence = payload.get("confidence")
            if route not in ROUTES:
                raise ValueError(f"LLM returned unknown route: {route!r}")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                raise ValueError("LLM self-reported confidence must be numeric between 0 and 1")
            return RouteDecisionResult(
                strategy=self.strategy,
                route=str(route),
                disposition="route",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=float(confidence),
                probabilities={},
                probability_source="self_reported_confidence",
                calibration_status="not_a_probability",
                latency_ms=(perf_counter() - started) * 1000.0,
                metadata={
                    "stages": ["llm"],
                    "model": payload.get("model"),
                    "input_tokens": int(payload.get("input_tokens", 0) or 0),
                    "output_tokens": int(payload.get("output_tokens", 0) or 0),
                },
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError, urllib.error.URLError) as exc:
            return RouteDecisionResult(
                strategy=self.strategy,
                route=None,
                disposition="error",
                probability=None,
                entropy_confidence=None,
                self_reported_confidence=None,
                probabilities={},
                probability_source="self_reported_confidence",
                calibration_status="not_a_probability",
                latency_ms=(perf_counter() - started) * 1000.0,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"stages": ["llm"]},
            )
