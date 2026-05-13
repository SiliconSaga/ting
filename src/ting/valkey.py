from functools import lru_cache

import redis

from .config import get_settings


@lru_cache
def get_valkey() -> redis.Redis:
    s = get_settings()
    # Bound connect + socket timeouts so a slow / unreachable Valkey can't
    # stall request paths (rate limiting, sessions, summary cache).
    return redis.Redis.from_url(
        s.valkey_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
