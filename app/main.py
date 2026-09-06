from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.query import router as query_router

app = FastAPI(title="Sift")
app.include_router(query_router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    # retrieve()/generate_answer() raise ValueError for invalid input (empty or
    # whitespace-only query), a client error, not a server fault worth a 500.
    return JSONResponse(status_code=422, content={"detail": str(exc)})
