import pytest
from sqlalchemy.exc import IntegrityError

from ting.db import get_engine, session_scope
from ting.models import Base, Code, Cohort, Proposal, Question, Response, School, Survey


@pytest.fixture(autouse=True)
def schema(settings_env):
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def _make_school(s, code="TST"):
    school = School(school_code=code, name="Test School", district="Test District")
    s.add(school)
    s.flush()
    return school


def test_create_cohort_and_code():
    with session_scope() as s:
        _make_school(s)
        c = Cohort(name="TEST-2026-spring", school_code="TST", batch_number=1)
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
        _make_school(s)
        c = Cohort(name="TEST-2026-spring", school_code="TST", batch_number=1)
        s.add(c)
        s.flush()
        code = Code(code_str="TST-AAAA-BBBB", cohort_id=c.cohort_id)
        prop = Proposal(slug="p1", title="P1", body="...", status="active")
        sv = Survey(slug="test-survey", title="Test Survey", cohort_id=c.cohort_id, display_order=1)
        s.add_all([code, prop, sv])
        s.flush()
        q = Question(slug="q1", type="likert", prompt="?",
                     payload={"statement": "x"}, display_order=1, survey_id=sv.survey_id)
        s.add(q)
        s.flush()
        s.add(Response(code_id=code.code_id, question_id=q.question_id, payload={"score": 4}))
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            code = s.query(Code).filter_by(code_str="TST-AAAA-BBBB").one()
            q = s.query(Question).filter_by(slug="q1").one()
            s.add(Response(code_id=code.code_id, question_id=q.question_id, payload={"score": 5}))
