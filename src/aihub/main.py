from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY, generate_latest, multiprocess
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import latency, request_size, requests, response_size
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from aihub.config import get_settings
from aihub.database import check_db, create_tables, init_db, pool_stats_collector
from aihub.logging_config import setup_logging
from aihub.routes.chat_history import router as chat_history_router
from aihub.routes.leaderboard import router as leaderboard_router
from aihub.routes.projects import router as projects_router

settings = get_settings()

# Prometheus multiprocess setup — must happen before any metrics are created
_METRICS_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
os.environ["PROMETHEUS_MULTIPROC_DIR"] = _METRICS_DIR
os.makedirs(_METRICS_DIR, exist_ok=True)

setup_logging(debug=settings.server.debug, silence_probes=settings.server.silence_probes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings)
    await create_tables()
    structlog.get_logger().info("worker_ready", pid=os.getpid())
    yield


app = FastAPI(title="aihub", version="0.1.0", root_path=settings.server.root_path, lifespan=lifespan)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        if request_id := request.headers.get("x-request-id", ""):
            structlog.contextvars.bind_contextvars(request_id=request_id)
        return await call_next(request)


app.add_middleware(RequestIDMiddleware)

app.include_router(projects_router)
app.include_router(leaderboard_router)
app.include_router(chat_history_router)


Instrumentator(
    should_group_status_codes=False,
    should_group_untemplated=True,
).add(
    latency(),
).add(
    request_size(),
).add(
    response_size(),
).add(
    requests(),
).instrument(app)


@app.get("/metrics")
async def metrics():
    # Use multiprocess collector only when .db files are present (production with multiple workers).
    # Falls back to the in-process registry in dev/test.
    db_files = list(Path(_METRICS_DIR).glob("*.db")) if os.path.isdir(_METRICS_DIR) else []
    if db_files:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY
    output = generate_latest(registry)

    # Pool stats are live point-in-time reads — they never go through the
    # multiprocess .db files, so they must always be appended separately.
    pool_registry = CollectorRegistry()
    pool_registry.register(pool_stats_collector)
    output += generate_latest(pool_registry)

    return StarletteResponse(content=output, media_type=CONTENT_TYPE_LATEST)


@app.get("/livez")
async def livez() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    if await check_db():
        return StarletteResponse(status_code=200)
    return StarletteResponse(status_code=503)


@app.get("/health")
async def health() -> dict:
    db_ok = await check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "components": {"postgres": "ok" if db_ok else "degraded"},
    }
