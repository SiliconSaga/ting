from functools import lru_cache

import redis

from .config import get_settings


@lru_cache
def get_valkey() -> redis.Redis:
    s = get_settings()
    return redis.Redis.from_url(s.valkey_url, decode_responses=True)
