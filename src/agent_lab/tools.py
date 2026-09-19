"""Allowlisted local tools with prompt-injection-aware output handling."""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .models import ToolResult

_INJECTION_MARKERS = re.compile(
    r"(?i)(ignore\s+(all|any|previous)|system\s+message|reveal\s+secret|developer\s+instruction)"
)


class ToolSecurityError(ValueError):
    """Raised when a tool call violates the local permission boundary."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    handler: Callable[[dict[str, Any]], Any]
    description: str
    read_only: bool = True
    requires_approval: bool = False
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False}
    )

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,48}", spec.name):
            raise ToolSecurityError("tool name is not allowlisted")
        self._tools[spec.name] = spec

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[name].schema() for name in self.names()]

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(name=name, ok=False, error="tool is not registered", blocked=True)
        if not isinstance(arguments, dict) or any(str(key).startswith("__") for key in arguments):
            return ToolResult(name=name, ok=False, error="unsafe tool arguments", blocked=True)
        try:
            output = spec.handler(arguments)
        except (ToolSecurityError, ValueError, ZeroDivisionError, SyntaxError, OverflowError) as exc:
            return ToolResult(name=name, ok=False, error=str(exc))
        serialized = str(output)
        if _INJECTION_MARKERS.search(serialized):
            return ToolResult(
                name=name,
                ok=False,
                error="tool output rejected: prompt-injection marker detected",
                blocked=True,
            )
        return ToolResult(name=name, ok=True, output=output)


_ALLOWED_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def _safe_calculate(arguments: dict[str, Any]) -> dict[str, Any]:
    expression = str(arguments.get("expression", "")).strip()
    if not expression or len(expression) > 80:
        raise ToolSecurityError("expression must be 1..80 characters")
    tree = ast.parse(expression, mode="eval")

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8:
                raise ToolSecurityError("exponent too large")
            return _ALLOWED_OPERATORS[type(node.op)](left, right)
        raise ToolSecurityError("expression contains a forbidden operation")

    result = visit(tree)
    if abs(result) > 10**12:
        raise ToolSecurityError("result exceeds local safety limit")
    return {"expression": expression, "result": result}


_FAQ = {
    "retry": "Retries are bounded, observable, and unsafe for non-idempotent actions without approval.",
    "mcp": "MCP separates a host, clients, and servers; tools should run with least privilege.",
    "rag": "Hybrid retrieval combines semantic similarity with lexical evidence before reranking.",
}


def _lookup_faq(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query", "")).strip().lower()
    if not query or len(query) > 240:
        raise ToolSecurityError("query must be 1..240 characters")
    for key, value in _FAQ.items():
        if key in query:
            return {"key": key, "answer": value}
    return {"key": "default", "answer": "No local FAQ entry matched the query."}


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "calculator",
            _safe_calculate,
            "safe arithmetic over numeric literals",
            parameters={
                "type": "object",
                "properties": {"expression": {"type": "string", "maxLength": 80}},
                "required": ["expression"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolSpec(
            "lookup_faq",
            _lookup_faq,
            "read-only local engineering FAQ",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "maxLength": 240}},
                "required": ["query"],
                "additionalProperties": False,
            },
        )
    )
    return registry
