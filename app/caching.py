import threading
import time
from collections import OrderedDict


class TTLCache[K, V]:
    """Small in-memory TTL + LRU cache.

    Single-process only, same single-instance assumption as
    app.rate_limiting.SlidingWindowRateLimiter. A size cap bounds memory
    growth independently of the TTL, since a low-traffic TTL alone would
    let entries accumulate for the full TTL window regardless of count.
    """

    def __init__(self, max_size: int, ttl_seconds: float) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            inserted_at, value = entry
            if now - inserted_at > self.ttl_seconds:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._store[key] = (time.monotonic(), value)
            self._store.move_to_end(key)
            while len(self._store) > self.max_size:
                self._store.popitem(last=False)

    def reset(self) -> None:
        with self._lock:
            self._store.clear()
