"""JWT authentication and scope/tenant claims for local enterprise tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt


class AuthenticationError(ValueError):
    """Raised when a bearer token is missing or invalid."""


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: tuple[str, ...]
    scopes: tuple[str, ...]
    issuer: str
    audience: str

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "*" in self.scopes

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


class JWTAuthenticator:
    def __init__(
        self,
        *,
        secret: str,
        issuer: str = "agent-engineering-sprint",
        audience: str = "agent-api",
        algorithms: tuple[str, ...] = ("HS256",),
    ) -> None:
        if not secret:
            raise ValueError("secret must not be empty")
        if not algorithms:
            raise ValueError("at least one algorithm is required")
        if any(algorithm.startswith("HS") for algorithm in algorithms) and len(secret.encode("utf-8")) < 32:
            raise ValueError("HMAC JWT secrets must be at least 32 bytes")
        self.secret = secret
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms

    def issue(
        self,
        *,
        subject: str,
        tenant_id: str,
        roles: list[str] | tuple[str, ...] = (),
        scopes: list[str] | tuple[str, ...] = (),
        expires_in_seconds: int = 900,
        algorithm: str | None = None,
    ) -> str:
        if expires_in_seconds <= 0:
            raise ValueError("expires_in_seconds must be positive")
        selected_algorithm = algorithm or self.algorithms[0]
        if selected_algorithm not in self.algorithms:
            raise ValueError("algorithm is not allowlisted")
        now = datetime.now(UTC)
        payload = {
            "sub": subject,
            "tenant_id": tenant_id,
            "roles": list(roles),
            "scopes": list(scopes),
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in_seconds),
        }
        return jwt.encode(payload, self.secret, algorithm=selected_algorithm)

    def decode(self, token: str) -> Principal:
        if not token.strip():
            raise AuthenticationError("token is empty")
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["sub", "tenant_id", "roles", "scopes", "exp", "iat"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError(str(exc)) from exc
        subject = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        roles = payload.get("roles")
        scopes = payload.get("scopes")
        if not all(isinstance(value, str) and value for value in (subject, tenant_id)):
            raise AuthenticationError("sub and tenant_id are required strings")
        subject_value = str(subject)
        tenant_value = str(tenant_id)
        if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
            raise AuthenticationError("roles must be a string list")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise AuthenticationError("scopes must be a string list")
        return Principal(
            subject=subject_value,
            tenant_id=tenant_value,
            roles=tuple(roles),
            scopes=tuple(scopes),
            issuer=str(payload["iss"]),
            audience=str(payload["aud"] if isinstance(payload["aud"], str) else payload["aud"][0]),
        )


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Bearer token required")
    token = authorization[7:].strip()
    if not token:
        raise AuthenticationError("Bearer token required")
    return token
