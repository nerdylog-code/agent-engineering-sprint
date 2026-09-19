"""Deterministic router used as an auditable baseline."""

from __future__ import annotations

import re

from .models import RouteDecision

_ARITHMETIC_RE = re.compile(r"[0-9][0-9\s+*/().%^-]*[0-9)]")


def route_request(objective: str, user_input: str) -> RouteDecision:
    text = f"{objective} {user_input}".lower()
    if any(word in text for word in ("rag", "document", "documento", "citation", "citação", "retriev")):
        return RouteDecision("rag_agent", None, "retrieval/citation language detected")
    if _ARITHMETIC_RE.search(text) or any(
        word in text for word in ("calculate", "calcule", "soma", "multiplique", "ferramenta", "tool")
    ):
        tool = "calculator" if _ARITHMETIC_RE.search(text) or any(
            word in text for word in ("calculate", "calcule", "soma", "multiplique")
        ) else "lookup_faq"
        return RouteDecision("tool_agent", tool, "explicit tool or arithmetic intent detected")
    return RouteDecision("general_agent", None, "no specialized intent detected")
