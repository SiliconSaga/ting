from sqlalchemy import func, select

from ..aggregation import borda, likert_histogram
from ..aggregation import nps as nps_calc
from ..db import session_scope
from ..models import (
    Code,
    Cohort,
    Comment,
    Endorsement,
    Pledge,
    Proposal,
    Question,
    Response,
    Survey,
)


def build_summary(*, cohort_name: str, survey_slug: str, grade_filter: int | None = None, n_floor: int = 10) -> dict:
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            return {"error": "cohort not found"}

        survey = s.scalar(select(Survey).where(Survey.slug == survey_slug))
        if survey is None:
            return {"error": "survey not found"}

        # Code filter (by grade if specified)
        code_q = select(Code.code_id).where(Code.cohort_id == cohort.cohort_id)
        if grade_filter is not None:
            code_q = code_q.where(Code.advocate_grade == grade_filter)
        eligible_code_ids = [r[0] for r in s.execute(code_q).all()]

        # Privacy floor: if filtered slice is small, return placeholder
        if grade_filter is not None and len(eligible_code_ids) < n_floor:
            return {"error": "slice-too-small", "n": len(eligible_code_ids), "floor": n_floor}

        n_respondents = s.scalar(
            select(func.count(func.distinct(Response.code_id)))
            .where(Response.code_id.in_(eligible_code_ids))
        ) or 0

        # Questions belonging to this survey
        questions = list(s.scalars(
            select(Question)
            .where(Question.survey_id == survey.survey_id)
            .order_by(Question.display_order)
        ))
        priorities = []
        nps_sections = []
        likert_sections = []

        for q in questions:
            resps = list(s.scalars(
                select(Response).where(
                    Response.question_id == q.question_id,
                    Response.code_id.in_(eligible_code_ids),
                )
            ))
            if q.type == "ranking":
                rankings = [r.payload.get("order", []) for r in resps]
                all_options = q.payload.get("proposal_slugs", [])
                scores = borda(rankings, all_options=all_options)
                # Normalize to *max possible* Borda points so a 100-bar means
                # "every voter put this first." Range becomes 0..100 in absolute
                # terms, exposing real differences between options.
                n_voters = len(rankings)
                n_options = len(all_options) if all_options else len(scores)
                max_possible = n_voters * (n_options - 1) if n_options > 1 else 0
                bars = [
                    {
                        "slug": slug,
                        "score": score,
                        "max_possible": max_possible,
                        "normalized": (score / max_possible * 100) if max_possible else 0,
                    }
                    for slug, score in sorted(scores.items(), key=lambda kv: -kv[1])
                ]
                priorities.append({"prompt": q.prompt, "slug": q.slug, "n": len(resps), "bars": bars})
            elif q.type == "nps":
                scores = [r.payload.get("score", 0) for r in resps]
                nps_sections.append({
                    "prompt": q.prompt, "slug": q.slug,
                    "subject": q.payload.get("subject", ""),
                    **nps_calc(scores),
                })
            elif q.type == "likert":
                scores = [r.payload.get("score", 0) for r in resps]
                hist = likert_histogram(scores)
                # JSON cache roundtrips dict keys to strings; convert
                # counts keys now so the template's lookups stay correct.
                hist["counts"] = {str(k): v for k, v in hist["counts"].items()}
                likert_sections.append({
                    "prompt": q.prompt, "slug": q.slug,
                    "statement": q.payload.get("statement", ""),
                    **hist,
                })

        # Pledge totals per proposal
        pledge_rows = s.execute(
            select(
                Pledge.proposal_id,
                func.sum(Pledge.amount_dollars).label("dollars"),
                func.sum(Pledge.hours_per_week).label("hours"),
                func.count(Pledge.code_id).label("n"),
            )
            .where(Pledge.code_id.in_(eligible_code_ids))
            .group_by(Pledge.proposal_id)
        ).all()
        proposal_titles = {p.proposal_id: (p.slug, p.title) for p in s.scalars(select(Proposal)).all()}
        pledges = [
            {
                "slug": proposal_titles.get(r.proposal_id, ("?", "?"))[0],
                "title": proposal_titles.get(r.proposal_id, ("?", "?"))[1],
                "dollars_per_month": float(r.dollars or 0),
                "hours_per_week": float(r.hours or 0),
                "n": int(r.n),
            }
            for r in sorted(pledge_rows, key=lambda r: -float(r.dollars or 0))
        ]

        # Top endorsed comments — scope to comments authored by eligible
        # codes (i.e. this cohort + grade slice) so unrelated cohorts'
        # comments never leak into this survey's summary.
        comment_rows = s.execute(
            select(
                Comment.comment_id, Comment.proposal_id, Comment.body,
                func.count(Endorsement.code_id).label("endorsements"),
            )
            .outerjoin(Endorsement, Endorsement.comment_id == Comment.comment_id)
            .where(
                Comment.hidden_at.is_(None),
                Comment.author_code_id.in_(eligible_code_ids),
            )
            .group_by(Comment.comment_id)
            .order_by(func.count(Endorsement.code_id).desc())
            .limit(5)
        ).all()
        top_comments = [
            {
                "body": r.body[:200],
                "endorsements": int(r.endorsements or 0),
                "proposal_slug": proposal_titles.get(r.proposal_id, ("?", "?"))[0],
            }
            for r in comment_rows
        ]

        return {
            "cohort": cohort_name,
            "survey": survey_slug,
            "n_respondents": int(n_respondents),
            "priorities": priorities,
            "nps": nps_sections,
            "likert": likert_sections,
            "pledges": pledges,
            "top_comments": top_comments,
        }
