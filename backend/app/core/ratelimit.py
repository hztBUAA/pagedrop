"""Lightweight in-memory rate limiter for sensitive endpoints.

MVP-grade: process-local sliding window keyed by client IP + bucket name.
Production should back this with Redis (see infra notes).
"""

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

_hits: dict[str, deque] = defaultdict(deque)


def _check(key: str, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()
    q = _hits[key]
    cutoff = now - window_seconds
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    return True


def rate_limit(bucket: str, limit: int, window_seconds: int = 60):
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        if not _check(f"{bucket}:{ip}", limit, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limited",
            )

    return Depends(dependency)


def reset() -> None:
    """Clear all counters (used by tests)."""
    _hits.clear()
