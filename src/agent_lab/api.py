"""FastAPI service boundary for health, agent runs, and cited RAG queries."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from production_rag.dataset import build_synthetic_corpus
from production_rag.ingest import ingest_documents
from production_rag.retrieval import HybridRetriever
from production_rag.storage import SQLiteCorpusStore

from . import __version__
from .auth import AuthenticationError, JWTAuthenticator, Principal, bearer_token
from .mcp_server import MCPServer
from .models import AgentRequest
from .orchestrator import AgentOrchestrator
from .rate_limit import FixedWindowRateLimiter
from .telemetry import Telemetry


class AgentRunPayload(BaseModel):
    objective: str = Field(min_length=1, max_length=500)
    user_input: str = Field(min_length=1, max_length=20_000)
    require_approval: bool = False


class RagQueryPayload(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)
    tenant_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    principal: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_:@.-]{1,128}$")


def create_app(
    *,
    api_token: str | None = None,
    rag_store_path: str | None = None,
    rate_limit_per_window: int | None = None,
    rate_limit_window_seconds: float = 60.0,
    jwt_secret: str | None = None,
    jwt_issuer: str = "agent-engineering-sprint",
    jwt_audience: str = "agent-api",
) -> FastAPI:
    app = FastAPI(title="Agent Engineering Sprint", version=__version__)
    app.state.telemetry = Telemetry(console=os.environ.get("AGENT_OTEL_CONSOLE", "0") == "1")
    app.state.agent = AgentOrchestrator(telemetry=app.state.telemetry)
    app.state.mcp_server = MCPServer()
    app.state.mcp_audit = []
    app.state.mcp_timeout_seconds = float(os.environ.get("AGENT_MCP_TIMEOUT_SECONDS", "5.0"))
    if app.state.mcp_timeout_seconds <= 0:
        raise ValueError("AGENT_MCP_TIMEOUT_SECONDS must be positive")
    documents = build_synthetic_corpus(100)
    chunks = ingest_documents(documents)
    configured_store_path = rag_store_path or os.environ.get("AGENT_RAG_STORE_PATH")
    app.state.rag_store = SQLiteCorpusStore(configured_store_path) if configured_store_path else None
    if app.state.rag_store is not None:
        app.state.rag_store.replace(documents, chunks)
        chunks = app.state.rag_store.load_chunks()
    app.state.retriever = HybridRetriever(chunks, telemetry=app.state.telemetry)
    app.state.provider_mode = os.environ.get("AGENT_PROVIDER_MODE", "offline-deterministic")
    app.state.api_token = api_token if api_token is not None else os.environ.get("AGENT_API_TOKEN")
    configured_jwt_secret = jwt_secret if jwt_secret is not None else os.environ.get("AGENT_JWT_SECRET")
    app.state.authenticator = (
        JWTAuthenticator(secret=configured_jwt_secret, issuer=jwt_issuer, audience=jwt_audience)
        if configured_jwt_secret
        else None
    )
    configured_rate = rate_limit_per_window
    if configured_rate is None:
        configured_rate = int(os.environ.get("AGENT_RATE_LIMIT", "60"))
    app.state.rate_limiter = FixedWindowRateLimiter(
        max_requests=configured_rate,
        window_seconds=rate_limit_window_seconds,
    )
    app.state.metrics = {
        "requests_total": 0,
        "agent_runs_total": 0,
        "rag_queries_total": 0,
        "rate_limited_total": 0,
    }

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"http-{uuid4().hex[:12]}"
        request.state.request_id = request_id
        request.state.principal = None
        app.state.metrics["requests_total"] += 1
        if (app.state.api_token or app.state.authenticator is not None) and request.url.path.startswith("/v1/"):
            authorization = request.headers.get("Authorization", "")
            if app.state.authenticator is not None:
                try:
                    request.state.principal = app.state.authenticator.decode(bearer_token(authorization))
                except AuthenticationError as exc:
                    return JSONResponse(
                        {"detail": "unauthorized", "reason": str(exc), "request_id": request_id},
                        status_code=401,
                        headers={"X-Request-ID": request_id},
                    )
            elif not hmac.compare_digest(authorization, f"Bearer {app.state.api_token}"):
                return JSONResponse(
                    {"detail": "unauthorized", "request_id": request_id},
                    status_code=401,
                    headers={"X-Request-ID": request_id},
                )
            principal = request.state.principal
            identity = (
                f"{principal.tenant_id}:{principal.subject}"
                if isinstance(principal, Principal)
                else authorization
            )
            allowed, retry_after = app.state.rate_limiter.allow(
                hashlib.sha256(identity.encode("utf-8")).hexdigest()
            )
            if not allowed:
                app.state.metrics["rate_limited_total"] += 1
                return JSONResponse(
                    {"detail": "rate limit exceeded", "request_id": request_id},
                    status_code=429,
                    headers={"X-Request-ID": request_id, "Retry-After": str(retry_after)},
                )
        with app.state.telemetry.span(
            "http.request",
            {"http.method": request.method, "http.route": request.url.path, "http.request_id": request_id},
        ):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "agent-engineering-sprint", "version": __version__}

    @app.get("/readyz")
    async def readyz():
        ready = hasattr(app.state, "agent") and hasattr(app.state, "retriever")
        payload = {
            "status": "ready" if ready else "not_ready",
            "provider_mode": app.state.provider_mode,
            "rag_documents": len({chunk.document_id for chunk in app.state.retriever.chunks}) if ready else 0,
            "rag_persistence": bool(app.state.rag_store),
        }
        return JSONResponse(payload, status_code=200 if ready else 503)

    @app.get("/metrics")
    async def metrics():
        lines = [
            "# TYPE agent_http_requests_total counter",
            f"agent_http_requests_total {app.state.metrics['requests_total']}",
            "# TYPE agent_runs_total counter",
            f"agent_runs_total {app.state.metrics['agent_runs_total']}",
            "# TYPE rag_queries_total counter",
            f"rag_queries_total {app.state.metrics['rag_queries_total']}",
            "# TYPE agent_rate_limited_total counter",
            f"agent_rate_limited_total {app.state.metrics['rate_limited_total']}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    @app.get("/v1/admin/mcp-audit")
    async def mcp_audit(request: Request):
        principal = request.state.principal
        if not isinstance(principal, Principal) or not principal.has_role("admin"):
            return JSONResponse({"detail": "admin role required"}, status_code=403)
        return {"audit": app.state.mcp_audit}

    @app.post("/v1/agent/runs")
    async def agent_run(request: Request, payload: AgentRunPayload):
        app.state.metrics["agent_runs_total"] += 1
        with app.state.telemetry.span("agent.run", {"tenant_id": getattr(request.state.principal, "tenant_id", None)}):
            result = app.state.agent.run(
                AgentRequest(
                    objective=payload.objective,
                    user_input=payload.user_input,
                    metadata={
                        "http_request_id": request.state.request_id,
                        "tenant_id": request.state.principal.tenant_id if isinstance(request.state.principal, Principal) else "",
                        "principal": request.state.principal.subject if isinstance(request.state.principal, Principal) else "",
                    },
                ),
                require_approval=payload.require_approval,
            )
        return {"request_id": request.state.request_id, "result": result.to_dict()}

    @app.post("/v1/rag/query")
    async def rag_query(request: Request, payload: RagQueryPayload):
        app.state.metrics["rag_queries_total"] += 1
        request_principal = request.state.principal
        tenant_id = payload.tenant_id
        principal = payload.principal
        if isinstance(request_principal, Principal):
            if tenant_id is not None and tenant_id != request_principal.tenant_id:
                return JSONResponse({"detail": "tenant mismatch"}, status_code=403)
            if principal is not None and principal != request_principal.subject:
                return JSONResponse({"detail": "principal mismatch"}, status_code=403)
            tenant_id = request_principal.tenant_id
            principal = request_principal.subject
        result = app.state.retriever.answer(
            payload.query,
            top_k=payload.top_k,
            tenant_id=tenant_id,
            principal=principal,
        )
        return result.to_dict()

    @app.post("/mcp")
    async def mcp_http(request: Request, payload: dict[str, object]):
        if app.state.authenticator is None:
            return JSONResponse({"detail": "MCP JWT authentication is not configured"}, status_code=503)
        try:
            principal = app.state.authenticator.decode(bearer_token(request.headers.get("Authorization")))
        except AuthenticationError as exc:
            return JSONResponse({"detail": "unauthorized", "reason": str(exc)}, status_code=401)
        method = payload.get("method")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        tool_name = params.get("name") if isinstance(params, dict) else None
        if method == "tools/call" and isinstance(tool_name, str) and not principal.has_scope(f"tools:{tool_name}"):
            app.state.mcp_audit.append(
                {"subject": principal.subject, "tenant_id": principal.tenant_id, "tool": tool_name, "allowed": False}
            )
            return JSONResponse({"detail": "tool scope denied"}, status_code=403)
        if method == "tools/call":
            try:
                with app.state.telemetry.span("tool.call", {"tool": tool_name, "tenant_id": principal.tenant_id}):
                    response = await asyncio.wait_for(
                        asyncio.to_thread(app.state.mcp_server.handle, payload),
                        timeout=app.state.mcp_timeout_seconds,
                    )
            except TimeoutError:
                app.state.mcp_audit.append(
                    {
                        "subject": principal.subject,
                        "tenant_id": principal.tenant_id,
                        "tool": tool_name,
                        "method": method,
                        "allowed": False,
                        "reason": "timeout",
                    }
                )
                return JSONResponse({"detail": "MCP tool timed out"}, status_code=504)
        else:
            response = app.state.mcp_server.handle(payload)
        app.state.mcp_audit.append(
            {
                "subject": principal.subject,
                "tenant_id": principal.tenant_id,
                "tool": tool_name,
                "method": method,
                "allowed": response is not None and "error" not in response,
            }
        )
        return response or {"jsonrpc": "2.0", "result": {}}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_lab.api:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
