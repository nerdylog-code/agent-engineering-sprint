"""Input/output safety checks for agent and tool boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyFinding:
    category: str
    severity: str
    start: int
    end: int
    redacted: str


@dataclass(frozen=True)
class SafetyReport:
    safe: bool
    action: str
    findings: tuple[SafetyFinding, ...]


_INJECTION_PATTERNS = (
    ("instruction_override", re.compile(r"(?i)ignore\s+(all|any|previous)\s+instructions?"), "high"),
    ("system_prompt_exfiltration", re.compile(r"(?i)(reveal|show|leak).{0,30}(system|developer)\s+prompt"), "high"),
    ("role_override", re.compile(r"(?i)you\s+are\s+now\s+(an?|the)\s+\w+"), "medium"),
    ("special_token", re.compile(r"<\|[^|]{1,40}\|>"), "high"),
)
_PII_PATTERNS = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "medium"),
    ("cpf", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "critical"),
    ("credit_card", re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"), "critical"),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), "critical"),
    ("secret_assignment", re.compile(r"(?i)\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+"), "critical"),
)


def scan_text(text: str, *, block_pii: bool = True) -> SafetyReport:
    findings: list[SafetyFinding] = []
    for category, pattern, severity in _INJECTION_PATTERNS + _PII_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(
                SafetyFinding(category, severity, match.start(), match.end(), _redact(match.group()))
            )
    has_high = any(item.severity in {"high", "critical"} for item in findings)
    has_pii = any(item.category in {"email", "cpf", "credit_card", "aws_key", "jwt", "secret_assignment"} for item in findings)
    blocked = has_high or (block_pii and has_pii)
    return SafetyReport(blocked is False, "BLOCK" if blocked else ("WARN" if findings else "ALLOW"), tuple(findings))


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:3]}…{value[-3:]}"
