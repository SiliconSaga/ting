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
    pipe = vk.pipeline()
    pipe.incr(key)
    pipe.expire(key, ttl_seconds)
    count, _ = pipe.execute()
    return int(count) <= limit


def allow_redemption(ip: str) -> bool:
    s = get_settings()
    return _bump(f"rl:red:{ip_hash(ip)}", 3600, s.rate_limit_redemption_per_hour)


def allow_write(code_id: str) -> bool:
    s = get_settings()
    return _bump(f"rl:w:{code_id}", 300, s.rate_limit_writes_per_5min)
