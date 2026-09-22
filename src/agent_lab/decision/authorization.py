from __future__ import annotations

from dataclasses import dataclass

SENSITIVE_ACTIONS = frozenset(
    {
        "email_send",
        "refund",
        "file_deletion",
        "fiscal_alteration",
        "external_write",
        "credential_operation",
    }
)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    route: str | None
    action: str


def authorize_action(route: str | None, action: str, *, approved: bool = False) -> AuthorizationDecision:
    normalized = action.strip().lower().replace(" ", "_")
    if normalized in SENSITIVE_ACTIONS and not approved:
        return AuthorizationDecision(
            allowed=False,
            requires_approval=True,
            reason="sensitive_action_requires_deterministic_approval",
            route=route,
            action=normalized,
        )
    if route != "tool_agent":
        return AuthorizationDecision(
            allowed=False,
            requires_approval=False,
            reason="route_not_authorized_for_tool_action",
            route=route,
            action=normalized,
        )
    return AuthorizationDecision(
        allowed=True,
        requires_approval=False,
        reason="allowlisted_tool_action",
        route=route,
        action=normalized,
    )
