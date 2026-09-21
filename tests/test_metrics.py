from app.metrics import Counters


def test_increment_starts_a_counter_at_one():
    counters = Counters()
    counters.increment("query.total")
    assert counters.snapshot()["query.total"] == 1


def test_increment_accumulates():
    counters = Counters()
    counters.increment("query.total")
    counters.increment("query.total")
    counters.increment("query.total", by=3)
    assert counters.snapshot()["query.total"] == 5


def test_snapshot_is_a_copy_not_a_live_view():
    counters = Counters()
    counters.increment("query.total")
    snapshot = counters.snapshot()
    counters.increment("query.total")
    assert snapshot["query.total"] == 1


def test_reset_clears_all_counters():
    counters = Counters()
    counters.increment("query.total")
    counters.reset()
    assert counters.snapshot() == {}
