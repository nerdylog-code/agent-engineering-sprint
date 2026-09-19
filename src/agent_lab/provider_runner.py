"""Provider-backed agent loop with real tool-call protocol validation."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import AgentRequest, RouteDecision, ToolResult
from .providers import OpenAICompatibleProvider, ProviderError, ProviderResponse
from .router import route_request
from .safety import SafetyReport, scan_text
from .telemetry import Telemetry
from .tools import ToolRegistry, default_registry
from .tracing import TraceCollector


@dataclass(frozen=True)
class ProviderRunResult:
    status: str
    trace_id: str
    route: RouteDecision
    final_response: ProviderResponse | None
    tool_results: tuple[ToolResult, ...]
    turns: int
    latency_seconds: float
    safety: SafetyReport
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        response = self.final_response
        return {
            "status": self.status,
            "trace_id": self.trace_id,
            "route": {"route": self.route.route, "selected_tool": self.route.selected_tool, "reason": self.route.reason},
            "final_response": {
                "content": response.content,
                "finish_reason": response.finish_reason,
                "tool_calls": [
                    {"id": call.call_id, "name": call.name, "arguments": call.arguments}
                    for call in response.tool_calls
                ],
                "usage": response.usage,
            } if response else None,
            "tool_results": [
                {"name": result.name, "ok": result.ok, "blocked": result.blocked, "error": result.error}
                for result in self.tool_results
            ],
            "turns": self.turns,
            "latency_seconds": self.latency_seconds,
            "safety": {
                "safe": self.safety.safe,
                "action": self.safety.action,
                "findings": [finding.category for finding in self.safety.findings],
            },
            "error": self.error,
        }


class ProviderAgentRunner:
    """Run a provider → tool → provider loop with explicit safety and turn bounds."""

    def __init__(
        self,
        provider: OpenAICompatibleProvider,
        *,
        registry: ToolRegistry | None = None,
        trace_path: str | Path | None = None,
        max_tool_turns: int = 3,
        telemetry: Telemetry | None = None,
    ) -> None:
        if not 1 <= max_tool_turns <= 5:
            raise ValueError("max_tool_turns must be between 1 and 5")
        self.provider = provider
        self.registry = registry or default_registry()
        self.trace_path = Path(trace_path) if trace_path else None
        self.max_tool_turns = max_tool_turns
        self.telemetry = telemetry or Telemetry()

    def run(self, request: AgentRequest, *, require_tool: bool = False) -> ProviderRunResult:
        started = time.perf_counter()
        with self.telemetry.span("router.route"):
            route = route_request(request.objective, request.user_input)
        safety = scan_text(request.user_input)
        tracer = TraceCollector(self.trace_path)
        tracer.record(
            agent=route.route,
            model=self.provider.model,
            event="provider_request",
            input_text=request.user_input,
            metadata={"base_url": self.provider.base_url, "safety_action": safety.action},
            status="blocked" if not safety.safe else "ok",
        )
        if not safety.safe:
            result = ProviderRunResult("blocked", tracer.trace_id, route, None, (), 0, time.perf_counter() - started, safety, "input blocked by safety gate")
            tracer.record(agent=route.route, model=self.provider.model, event="final", status="blocked", error=result.error)
            tracer.flush()
            return result

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are a tool-using assistant. Use only declared tools and return a concise final answer."},
            {"role": "user", "content": request.user_input},
        ]
        tool_results: list[ToolResult] = []
        for turn in range(1, self.max_tool_turns + 1):
            try:
                with self.telemetry.span(
                    "provider.call",
                    {"model": self.provider.model, "turn": turn, "retry_count": turn - 1},
                ):
                    response = self.provider.chat(
                        messages,
                        tools=self.registry.schemas(),
                        tool_choice="required" if require_tool and turn == 1 else "auto",
                        temperature=0.0,
                        max_tokens=256,
                    )
            except ProviderError as exc:  # provider boundary becomes evidence, not an unhandled response
                error = type(exc).__name__ + ": " + str(exc)
                tracer.record(agent=route.route, model=self.provider.model, event="provider_response", status="error", error=error, retry_count=turn - 1)
                tracer.flush()
                return ProviderRunResult("failed", tracer.trace_id, route, None, tuple(tool_results), turn, time.perf_counter() - started, safety, error)
            tracer.record(
                agent=route.route,
                model=response.model,
                event="provider_response",
                input_text=request.user_input,
                output_text=response.content,
                latency=response.latency_seconds,
                status="tool_call" if response.has_tool_calls else "final",
                retry_count=turn - 1,
                metadata={"finish_reason": response.finish_reason, "tool_calls": len(response.tool_calls), "usage": response.usage},
            )
            if response.has_tool_calls:
                assistant_calls = [
                    {"id": call.call_id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
                    for call in response.tool_calls
                ]
                messages.append({"role": "assistant", "content": response.content or None, "tool_calls": assistant_calls})
                for call in response.tool_calls:
                    with self.telemetry.span("tool.call", {"tool": call.name, "turn": turn}):
                        tool_result = self.registry.call(call.name, call.arguments)
                    tool_results.append(tool_result)
                    tracer.record(
                        agent=route.route,
                        model=response.model,
                        event="tool_call",
                        tool=call.name,
                        input_text=json.dumps(call.arguments),
                        output_text=json.dumps(tool_result.output, ensure_ascii=False) if tool_result.ok else "",
                        status="ok" if tool_result.ok else ("blocked" if tool_result.blocked else "error"),
                        error=tool_result.error,
                        retry_count=turn - 1,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "name": call.name,
                            "content": json.dumps(
                                {"ok": tool_result.ok, "output": tool_result.output, "error": tool_result.error},
                                ensure_ascii=False,
                            ),
                        }
                    )
                continue
            if require_tool and not tool_results:
                error = "provider returned final content without the required tool call"
                tracer.record(agent=route.route, model=response.model, event="final", status="error", error=error)
                tracer.flush()
                return ProviderRunResult("failed", tracer.trace_id, route, response, (), turn, time.perf_counter() - started, safety, error)
            tracer.record(agent=route.route, model=response.model, event="final", output_text=response.content, status="completed")
            tracer.flush()
            return ProviderRunResult("completed", tracer.trace_id, route, response, tuple(tool_results), turn, time.perf_counter() - started, safety)
        error = f"tool loop exceeded max_tool_turns={self.max_tool_turns}"
        tracer.record(agent=route.route, model=self.provider.model, event="final", status="error", error=error)
        tracer.flush()
        return ProviderRunResult("failed", tracer.trace_id, route, None, tuple(tool_results), self.max_tool_turns, time.perf_counter() - started, safety, error)
