from app.rate_limiting import SlidingWindowRateLimiter


def test_allows_requests_up_to_the_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60)

    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is True


def test_blocks_requests_past_the_limit_within_the_window():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60)

    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is False


def test_keys_are_independent():
    # Two accounts sharing the same deployment don't share a limit — the
    # whole point is protecting the shared Groq quota per account, not a
    # single global ceiling that one noisy account could exhaust for everyone.
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)

    assert limiter.allow("user-a") is True
    assert limiter.allow("user-b") is True
    assert limiter.allow("user-a") is False
    assert limiter.allow("user-b") is False


def test_old_hits_expire_out_of_the_window():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=0.05)

    assert limiter.allow("user-a") is True
    assert limiter.allow("user-a") is False

    import time

    time.sleep(0.06)
    assert limiter.allow("user-a") is True


def test_reset_clears_all_state():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60)
    limiter.allow("user-a")
    assert limiter.allow("user-a") is False

    limiter.reset()

    assert limiter.allow("user-a") is True
