"""Per-IP sliding-window rate limiter (abuse-hardening ground rule).

Stdlib only and framework agnostic, so the exact limiter used in production is
unit-testable without booting the app. The caller builds the key (for example
"login:" + client_ip) and maps a False result onto an HTTP 429 response.
"""
import collections
import time as _time

_HITS = collections.defaultdict(list)


def rate_ok(key, limit, window=60, now=None):
    """True if `key` is under `limit` hits in the last `window` seconds.

    Records the hit when it is allowed. Pass `now` in tests for determinism.
    """
    now = _time.time() if now is None else now
    q = _HITS[key]
    cut = now - window
    while q and q[0] < cut:
        q.pop(0)
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def reset():
    """Clear all counters (used by tests)."""
    _HITS.clear()
