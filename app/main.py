import time
import uuid

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import structlog

from app.api.v1 import auth, applications, ingestion, search, clusters, rules, channels, alerts, analytics, dashboard
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine

setup_logging()
logger = structlog.get_logger(__name__)

REQUEST_COUNT = Counter("pulsemetrics_http_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("pulsemetrics_http_request_duration_seconds", "HTTP request latency", ["path"])

app = FastAPI(
    title="PulseMetrics",
    description="AI-powered log monitoring and alerting",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(
        method=request.method,
        path=request.url.path,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(path=request.url.path).observe(duration)

    response.headers["X-Correlation-ID"] = correlation_id
    return response


PREFIX = "/api/v1"
app.include_router(auth.router, prefix=PREFIX)
app.include_router(applications.router, prefix=PREFIX)
app.include_router(ingestion.router, prefix=PREFIX)
app.include_router(search.router, prefix=PREFIX)
app.include_router(clusters.router, prefix=PREFIX)
app.include_router(rules.router, prefix=PREFIX)
app.include_router(channels.router, prefix=PREFIX)
app.include_router(alerts.router, prefix=PREFIX)
app.include_router(analytics.router, prefix=PREFIX)
app.include_router(dashboard.router)


@app.get("/health")
async def health() -> dict:
    from sqlalchemy import text
    from app.db.session import AsyncSessionLocal
    db_ok = False
    redis_ok = False

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    status = "ok" if (db_ok and redis_ok) else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok}


@app.get("/health/ready")
async def readiness() -> dict:
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root() -> dict:
    return {
        "service": "PulseMetrics",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/health",
    }


@app.get("/dashboard")
async def dashboard_redirect() -> Response:
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")
