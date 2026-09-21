import time

from app.caching import TTLCache


def test_get_returns_none_for_missing_key():
    cache: TTLCache[str, str] = TTLCache(max_size=10, ttl_seconds=60)
    assert cache.get("missing") is None


def test_set_then_get_returns_the_stored_value():
    cache: TTLCache[str, str] = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("key", "value")
    assert cache.get("key") == "value"


def test_entry_expires_after_ttl():
    cache: TTLCache[str, str] = TTLCache(max_size=10, ttl_seconds=0.05)
    cache.set("key", "value")
    time.sleep(0.06)
    assert cache.get("key") is None


def test_size_cap_evicts_the_least_recently_used_entry():
    cache: TTLCache[str, str] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")

    # "a" was inserted first and never touched again, so it's the one
    # evicted when the cache exceeds its size cap, not "b".
    assert cache.get("a") is None
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_get_refreshes_recency_so_it_survives_eviction():
    cache: TTLCache[str, str] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.get("a")  # touch "a" so "b" becomes the least-recently-used one
    cache.set("c", "3")

    assert cache.get("a") == "1"
    assert cache.get("b") is None


def test_reset_clears_all_entries():
    cache: TTLCache[str, str] = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("key", "value")
    cache.reset()
    assert cache.get("key") is None
