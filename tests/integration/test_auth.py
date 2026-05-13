import time
from uuid import uuid4

from ting.auth import clear_session, mint_session, resolve_session


def test_session_roundtrip(settings_env):
    code_id = uuid4()
    sid = mint_session(code_id)
    assert isinstance(sid, str) and len(sid) >= 32
    resolved = resolve_session(sid)
    assert resolved == code_id


def test_session_expires(settings_env):
    code_id = uuid4()
    sid = mint_session(code_id, ttl_seconds=1)
    time.sleep(1.5)
    assert resolve_session(sid) is None


def test_session_clear(settings_env):
    code_id = uuid4()
    sid = mint_session(code_id)
    clear_session(sid)
    assert resolve_session(sid) is None
