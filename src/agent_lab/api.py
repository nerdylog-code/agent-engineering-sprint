"""FastAPI service boundary for health, agent runs, and cited RAG queries."""

from __future__ import annotations

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
from .models import AgentRequest
from .orchestrator import AgentOrchestrator
from .rate_limit import FixedWindowRateLimiter


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
) -> FastAPI:
    app = FastAPI(title="Agent Engineering Sprint", version=__version__)
    app.state.agent = AgentOrchestrator()
    documents = build_synthetic_corpus(100)
    chunks = ingest_documents(documents)
    configured_store_path = rag_store_path or os.environ.get("AGENT_RAG_STORE_PATH")
    app.state.rag_store = SQLiteCorpusStore(configured_store_path) if configured_store_path else None
    if app.state.rag_store is not None:
        app.state.rag_store.replace(documents, chunks)
        chunks = app.state.rag_store.load_chunks()
    app.state.retriever = HybridRetriever(chunks)
    app.state.provider_mode = os.environ.get("AGENT_PROVIDER_MODE", "offline-deterministic")
    app.state.api_token = api_token if api_token is not None else os.environ.get("AGENT_API_TOKEN")
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
        app.state.metrics["requests_total"] += 1
        if app.state.api_token and request.url.path.startswith("/v1/"):
            authorization = request.headers.get("Authorization", "")
            if not hmac.compare_digest(authorization, f"Bearer {app.state.api_token}"):
                return JSONResponse(
                    {"detail": "unauthorized", "request_id": request_id},
                    status_code=401,
                    headers={"X-Request-ID": request_id},
                )
            identity = authorization
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

    @app.post("/v1/agent/runs")
    async def agent_run(request: Request, payload: AgentRunPayload):
        app.state.metrics["agent_runs_total"] += 1
        result = app.state.agent.run(
            AgentRequest(
                objective=payload.objective,
                user_input=payload.user_input,
                metadata={"http_request_id": request.state.request_id},
            ),
            require_approval=payload.require_approval,
        )
        return {"request_id": request.state.request_id, "result": result.to_dict()}

    @app.post("/v1/rag/query")
    async def rag_query(request: Request, payload: RagQueryPayload):
        app.state.metrics["rag_queries_total"] += 1
        result = app.state.retriever.answer(
            payload.query,
            top_k=payload.top_k,
            tenant_id=payload.tenant_id,
            principal=payload.principal,
        )
        return result.to_dict()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_lab.api:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
