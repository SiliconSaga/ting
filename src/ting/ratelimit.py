import hashlib
import hmac

from .config import get_settings
from .valkey import get_valkey


def ip_hash(ip: str) -> str:
    s = get_settings()
    mac = hmac.new(s.session_secret.encode(), ip.encode(), hashlib.sha256)
    return mac.hexdigest()[:16]


def _bump(key: str, ttl_seconds: int, limit: int) -> bool:
    vk = get_valkey()
    # Set the TTL only on first creation (NX). Calling EXPIRE on every
    # hit produces a sliding window — a determined retrier could keep
    # the key alive but never trip the limit. Fixed window matches the
    # intent of "N attempts per hour."
    pipe = vk.pipeline()
    pipe.incr(key)
    pipe.expire(key, ttl_seconds, nx=True)
    count, _ = pipe.execute()
    return int(count) <= limit


def allow_redemption(ip: str) -> bool:
    s = get_settings()
    return _bump(f"rl:red:{ip_hash(ip)}", 3600, s.rate_limit_redemption_per_hour)


def allow_write(code_id: str) -> bool:
    s = get_settings()
    return _bump(f"rl:w:{code_id}", 300, s.rate_limit_writes_per_5min)
