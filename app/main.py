import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.query import router as query_router
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("sift.request")

app = FastAPI(title="Sift")
app.include_router(auth_router)
app.include_router(query_router)


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
