from dataclasses import dataclass

from django.core.cache import cache


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    remaining: int
    retry_after: int


def consume(key: str, limit: int, window_seconds: int) -> LimitResult:
    cache_key = f"rate:{key}"
    if cache.add(cache_key, 1, timeout=window_seconds):
        count = 1
    else:
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=window_seconds)
            count = 1
    return LimitResult(count <= limit, max(limit - count, 0), window_seconds)
