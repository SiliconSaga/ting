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
        assert s.query(Code).count() == 1


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
            code = s.query(Code).one()
            q = s.query(Question).one()
            s.add(Response(code_id=code.code_id, question_id=q.question_id, payload={"score": 5}))
