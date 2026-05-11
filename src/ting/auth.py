import secrets
from uuid import UUID

from .valkey import get_valkey

SESSION_TTL_SECONDS = 24 * 3600
SESSION_PREFIX = "sess:"


def mint_session(code_id: UUID, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    sid = secrets.token_urlsafe(32)
    get_valkey().setex(f"{SESSION_PREFIX}{sid}", ttl_seconds, str(code_id))
    return sid


def resolve_session(sid: str) -> UUID | None:
    raw = get_valkey().get(f"{SESSION_PREFIX}{sid}")
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def clear_session(sid: str) -> None:
    get_valkey().delete(f"{SESSION_PREFIX}{sid}")
