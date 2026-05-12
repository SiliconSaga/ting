import pytest
from sqlalchemy.exc import IntegrityError
from ting.db import get_engine, session_scope
from ting.models import Base, Cohort, Code, Proposal, Question, Response


@pytest.fixture(autouse=True)
def schema(settings_env):
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_create_cohort_and_code():
    with session_scope() as s:
        c = Cohort(name="TEST-2026-spring")
        s.add(c)
        s.flush()
        code = Code(code_str="TST-AAAA-BBBB", cohort_id=c.cohort_id)
        s.add(code)
    with session_scope() as s:
        # Scope by code_str so the assertion is immune to leftover rows from
        # other tests' fixtures that share the test database.
        assert s.query(Code).filter_by(code_str="TST-AAAA-BBBB").count() == 1


def test_response_unique_per_code_question():
    with session_scope() as s:
        c = Cohort(name="TEST-2026-spring")
        s.add(c); s.flush()
        code = Code(code_str="TST-AAAA-BBBB", cohort_id=c.cohort_id)
        prop = Proposal(slug="p1", title="P1", body="...", status="active")
        q = Question(slug="q1", type="likert", prompt="?",
                     payload={"statement": "x"}, display_order=1, cohort_id=c.cohort_id)
        s.add_all([code, prop, q]); s.flush()
        s.add(Response(code_id=code.code_id, question_id=q.question_id, payload={"score": 4}))
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            code = s.query(Code).filter_by(code_str="TST-AAAA-BBBB").one()
            q = s.query(Question).filter_by(slug="q1").one()
            s.add(Response(code_id=code.code_id, question_id=q.question_id, payload={"score": 5}))
