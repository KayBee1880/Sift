import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.db.models import User
from app.metrics import metrics


class SlidingWindowRateLimiter:
    """In-memory, per-key sliding-window limiter.

    Single-process only: correct for this project's single Render instance.
    A multi-instance deployment would need a shared store (e.g. Redis)
    instead — not built, since there's only one instance to protect.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_settings = get_settings()
query_rate_limiter = SlidingWindowRateLimiter(
    max_requests=_settings.rate_limit_max_requests,
    window_seconds=_settings.rate_limit_window_seconds,
)


def enforce_query_rate_limit(current_user: User = Depends(get_current_user)) -> None:
    if not query_rate_limiter.allow(current_user.username):
        metrics.increment("query.rate_limited")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: max {query_rate_limiter.max_requests} requests "
                f"per {query_rate_limiter.window_seconds:.0f}s per account. Try again shortly."
            ),
        )
