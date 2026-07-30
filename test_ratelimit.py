"""Abuse test for the per-IP limiter (ground rule: assert rapid requests -> 429).

Runs with plain `python3 test_ratelimit.py`, no Flask or pytest needed, because
it exercises the exact production limiter in ratelimit.py. The login route maps
a False result onto HTTP 429, so "blocked after the limit" is the 429 case.
"""
from ratelimit import rate_ok, reset


def test_blocks_after_limit():
    reset()
    # 20 allowed (login limit), the 21st is refused -> 429.
    assert all(rate_ok("login:1.2.3.4", 20, 60, now=100) for _ in range(20))
    assert rate_ok("login:1.2.3.4", 20, 60, now=100) is False


def test_window_resets():
    reset()
    assert rate_ok("k", 1, 60, now=0) is True
    assert rate_ok("k", 1, 60, now=30) is False   # still inside the window
    assert rate_ok("k", 1, 60, now=61) is True     # old hit expired


def test_per_ip_isolation():
    reset()
    assert rate_ok("login:1.1.1.1", 1, 60, now=0) is True
    assert rate_ok("login:2.2.2.2", 1, 60, now=0) is True  # different IP unaffected
    assert rate_ok("login:1.1.1.1", 1, 60, now=0) is False


if __name__ == "__main__":
    test_blocks_after_limit()
    test_window_resets()
    test_per_ip_isolation()
    print("ratelimit: all tests passed")
