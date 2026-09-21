import pytest

import app.rate_limiting as rate_limiting_module
from app.api.routes import query as query_route
from app.metrics import metrics


@pytest.fixture(autouse=True)
def _reset_shared_singletons():
    # query_rate_limiter, _answer_cache, and metrics are module-level
    # singletons shared across the whole test session (they back real
    # per-process state in production, so they can't be request-scoped).
    # Resetting before every test keeps one test's hits, cached answers, or
    # counts from leaking into another and making results depend on test
    # order rather than on the behavior actually being tested.
    rate_limiting_module.query_rate_limiter.reset()
    query_route._answer_cache.reset()
    metrics.reset()
    yield
