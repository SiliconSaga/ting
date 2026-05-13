"""fk_indexes_and_question_type_check

Adds:
- FK-column indexes on `comments.proposal_id`, `comments.author_code_id`,
  `questions.survey_id`, `surveys.cohort_id` — speeds up the lookups
  the summary service runs per cohort/survey.
- CHECK constraint on `questions.type` enforcing the
  `ranking | nps | likert` enum at the DB layer (the loader already
  validates; this is belt-and-suspenders).

Revision ID: 7dd7faa53a6d
Revises: 6d7670f9f395
Create Date: 2026-05-13 08:02:37.165009

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7dd7faa53a6d"
down_revision: str | None = "6d7670f9f395"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_comments_proposal_id"), "comments", ["proposal_id"], unique=False,
    )
    op.create_index(
        op.f("ix_comments_author_code_id"), "comments", ["author_code_id"], unique=False,
    )
    op.create_index(
        op.f("ix_questions_survey_id"), "questions", ["survey_id"], unique=False,
    )
    op.create_index(
        op.f("ix_surveys_cohort_id"), "surveys", ["cohort_id"], unique=False,
    )
    op.create_check_constraint(
        "ck_questions_type",
        "questions",
        "type IN ('ranking', 'nps', 'likert')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_questions_type", "questions", type_="check")
    op.drop_index(op.f("ix_surveys_cohort_id"), table_name="surveys")
    op.drop_index(op.f("ix_questions_survey_id"), table_name="questions")
    op.drop_index(op.f("ix_comments_author_code_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_proposal_id"), table_name="comments")
