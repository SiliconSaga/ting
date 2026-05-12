import pytest
from pathlib import Path
from ting.db import session_scope
from ting.models import Base, Code, Response, Question, Pledge, Endorsement, Comment, Proposal
from ting.db import get_engine
from ting.services.seed_loader import load_seed
from ting.services.summary_service import build_summary


@pytest.fixture(autouse=True)
def schema(settings_env):
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def _add_code(s, cohort_id, code_str="AAA-BBBB-CCCC", grade=None):
    c = Code(code_str=code_str, cohort_id=cohort_id, advocate_grade=grade)
    s.add(c); s.flush()
    return c


def test_summary_has_sections():
    load_seed(Path("seeds/example.yaml"))
    summary = build_summary(cohort_name="MPE-2026-spring-pilot", survey_slug="spring-pilot-general")
    assert "priorities" in summary  # ranking questions
    assert "nps" in summary
    assert "likert" in summary
    assert "pledges" in summary
    assert "top_comments" in summary
    assert "n_respondents" in summary


def test_summary_unknown_survey():
    load_seed(Path("seeds/example.yaml"))
    result = build_summary(cohort_name="MPE-2026-spring-pilot", survey_slug="nonexistent-survey")
    assert result.get("error") == "survey not found"
