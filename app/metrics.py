import threading


class Counters:
    """Minimal in-process counters, exposed via GET /metrics.

    Deliberately not Prometheus/OpenTelemetry: this project's scale has no
    measured need for that infrastructure yet. A JSON counter snapshot is
    the honest ceiling for "metrics" here, one step past structured logs,
    not a claim of production-grade observability.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}

    def increment(self, name: str, by: int = 1) -> None:
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + by

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counts)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


metrics = Counters()
