import pytest


@pytest.fixture(autouse=True)
def schema_only(settings_env):
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_bulletin_post():
    from ting.cli import bulletin_post
    bulletin_post(body="Test bulletin", posted_by="tester")
    from ting.db import session_scope
    from ting.models import Bulletin
    with session_scope() as s:
        assert s.query(Bulletin).filter_by(posted_by="tester").count() == 1
