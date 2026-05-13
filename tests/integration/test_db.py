from sqlalchemy import text

from ting.db import get_engine, session_scope


def test_engine_connects(settings_env):
    eng = get_engine()
    with eng.connect() as conn:
        r = conn.execute(text("SELECT 1"))
        assert r.scalar() == 1


def test_session_scope_commits(settings_env):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE smoke (v INT)"))
    with session_scope() as s:
        s.execute(text("INSERT INTO smoke (v) VALUES (42)"))
    with eng.connect() as conn:
        r = conn.execute(text("SELECT v FROM smoke"))
        assert r.scalar() == 42
