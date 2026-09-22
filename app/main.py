import logging
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.query import router as query_router
from app.logging_config import setup_logging
from app.metrics import metrics

setup_logging()
logger = logging.getLogger("sift.request")

app = FastAPI(title="Sift")
app.include_router(auth_router)
app.include_router(query_router)


@app.get("/health")
def health() -> dict:
    # Unauthenticated on purpose: a load balancer or uptime monitor hitting
    # this shouldn't need credentials, standard practice for a health check.
    return {"status": "ok"}


@app.get("/metrics")
def get_metrics() -> dict:
    # A JSON counter snapshot, not Prometheus/OpenTelemetry: this project's
    # scale has no measured need for that infrastructure. See app/metrics.py.
    return metrics.snapshot()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # retrieve()/generate_answer() raise ValueError for invalid input (empty or
    # whitespace-only query), a client error, not a server fault worth a 500.
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(httpx.HTTPStatusError)
async def groq_unavailable_handler(request: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    # _call_groq() already retries transient errors (see GROQ_MAX_RETRIES);
    # this only fires once retries are exhausted (real, confirmed under
    # concurrent load on 2026-09-21, not hypothetical: 4 concurrent
    # generation calls exceeded Groq's free-tier rate limit and stayed
    # rate-limited past the retry budget). A clean, expected 503 for the
    # caller, not an opaque, unhandled 500 leaking an httpx traceback.
    logger.warning("generation backend unavailable", extra={"error": str(exc)})
    return JSONResponse(
        status_code=503,
        content={"detail": "The generation service is temporarily unavailable. Try again shortly."},
    )
