"""Small, deterministic orchestrator that makes agent behavior measurable."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from .models import (
    AgentRequest,
    AgentRunResult,
    RouteDecision,
    StructuredOutput,
    StructuredOutputError,
    ToolResult,
)
from .router import route_request
from .telemetry import Telemetry
from .tools import ToolRegistry, default_registry
from .tracing import TraceCollector

ApprovalCallback = Callable[[StructuredOutput], bool]


class AgentOrchestrator:
    """Offline orchestrator with explicit route, tool, retry, and approval stages."""

    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        model: str = "offline-deterministic-v1",
        trace_path: str | Path | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self.registry = registry or default_registry()
        self.model = model
        self.trace_path = Path(trace_path) if trace_path else None
        self.telemetry = telemetry or Telemetry()

    def run(
        self,
        request: AgentRequest,
        *,
        max_retries: int = 2,
        require_approval: bool = False,
        approval: ApprovalCallback | None = None,
        invalid_attempts: int = 0,
    ) -> AgentRunResult:
        if max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")
        if invalid_attempts < 0:
            raise ValueError("invalid_attempts must not be negative")
        tracer = TraceCollector(self.trace_path)
        started = time.perf_counter()
        with self.telemetry.span("router.route"):
            decision = route_request(request.objective, request.user_input)
        tracer.record(
            agent=decision.route,
            model=self.model,
            event="route",
            input_text=f"{request.objective} {request.user_input}",
            output_text=decision.route,
            metadata={"reason": decision.reason, "selected_tool": decision.selected_tool},
        )

        tool_result = self._run_tool(decision, request, tracer)
        retries = 0
        response: StructuredOutput | None = None
        error: str | None = None
        for attempt in range(max_retries + 1):
            retries = attempt
            candidate = self._generate_candidate(decision, request, tool_result, require_approval)
            if attempt < invalid_attempts:
                candidate["confidence"] = "invalid"
            try:
                response = StructuredOutput.from_dict(candidate)
                tracer.record(
                    agent=decision.route,
                    model=self.model,
                    event="structured_output",
                    input_text=request.user_input,
                    output_text=response.answer,
                    retry_count=attempt,
                    metadata={"valid": True},
                )
                break
            except StructuredOutputError as exc:
                error = str(exc)
                tracer.record(
                    agent=decision.route,
                    model=self.model,
                    event="structured_output",
                    input_text=request.user_input,
                    retry_count=attempt,
                    status="retry" if attempt < max_retries else "error",
                    error=error,
                    metadata={"valid": False},
                )
        if response is None:
            status = "failed"
            result = AgentRunResult(
                run_id=tracer.run_id,
                trace_id=tracer.trace_id,
                status=status,
                response=None,
                route=decision,
                tool_result=tool_result,
                retries=retries,
                latency=round(time.perf_counter() - started, 6),
                error=error or "structured output unavailable",
            )
            tracer.record(
                agent=decision.route,
                model=self.model,
                event="final",
                status="error",
                retry_count=retries,
                error=result.error,
            )
            tracer.flush()
            return result

        status = "completed"
        approved = not response.needs_approval
        if response.needs_approval:
            if approval is None:
                status = "awaiting_approval"
                approved = False
            elif approval(response):
                status = "completed"
                approved = True
            else:
                status = "rejected"
                approved = False
        if not approved and status == "completed":
            status = "awaiting_approval"
        tracer.record(
            agent=decision.route,
            model=self.model,
            event="approval" if response.needs_approval else "final",
            output_text=response.answer,
            status=status,
            retry_count=retries,
            metadata={"approved": approved},
        )
        result = AgentRunResult(
            run_id=tracer.run_id,
            trace_id=tracer.trace_id,
            status=status,
            response=response,
            route=decision,
            tool_result=tool_result,
            retries=retries,
            latency=round(time.perf_counter() - started, 6),
        )
        tracer.flush()
        return result

    def _run_tool(self, decision: RouteDecision, request: AgentRequest, tracer: TraceCollector) -> ToolResult | None:
        if not decision.selected_tool:
            return None
        arguments = self._tool_arguments(decision.selected_tool, request.user_input)
        started = time.perf_counter()
        with self.telemetry.span("tool.call", {"tool": decision.selected_tool, "model": self.model}):
            result = self.registry.call(decision.selected_tool, arguments)
        tracer.record(
            agent=decision.route,
            model=self.model,
            event="tool_call",
            tool=decision.selected_tool,
            input_text=str(arguments),
            output_text=str(result.output) if result.ok else "",
            latency=time.perf_counter() - started,
            status="ok" if result.ok else ("blocked" if result.blocked else "error"),
            error=result.error,
            metadata={"read_only": True},
        )
        return result

    @staticmethod
    def _tool_arguments(tool: str, user_input: str) -> dict[str, str]:
        if tool == "calculator":
            expression = user_input
            for marker in ("calcule", "calculate", "soma", "multiplique"):
                expression = expression.lower().replace(marker, " ")
            return {"expression": expression.strip(" :?=")}
        return {"query": user_input}

    @staticmethod
    def _generate_candidate(
        decision: RouteDecision,
        request: AgentRequest,
        tool_result: ToolResult | None,
        require_approval: bool,
    ) -> dict[str, object]:
        if decision.route == "tool_agent" and tool_result is not None:
            if tool_result.ok:
                answer = f"Ferramenta `{tool_result.name}` executada com segurança: {tool_result.output}."
                confidence = 0.98
            else:
                answer = f"A ferramenta `{tool_result.name}` não foi executada: {tool_result.error}."
                confidence = 0.35
        elif decision.route == "rag_agent":
            answer = "A solicitação foi encaminhada ao Production RAG Lab para recuperar evidências e citações."
            confidence = 0.82
        else:
            answer = f"Solicitação recebida para o objetivo: {request.objective.strip()}."
            confidence = 0.78
        return {
            "answer": answer,
            "route": decision.route,
            "selected_tool": decision.selected_tool,
            "confidence": confidence,
            "needs_approval": require_approval,
            "citations": [],
        }


def demo(trace_path: str | Path | None = None) -> AgentRunResult:
    orchestrator = AgentOrchestrator(trace_path=trace_path)
    return orchestrator.run(
        AgentRequest(objective="validate CI/CD tool routing", user_input="calcule 7 * 6")
    )
