from collections import defaultdict
from sqlalchemy import select, func

from ..aggregation import borda, nps as nps_calc, likert_histogram
from ..db import session_scope
from ..models import (
    Cohort, Code, Question, Response, Proposal, Comment, Endorsement, Pledge,
)


def build_summary(*, cohort_name: str, grade_filter: int | None = None, n_floor: int = 10) -> dict:
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            return {"error": "cohort not found"}

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

        # Questions grouped by type
        questions = list(s.scalars(
            select(Question).where(Question.cohort_id == cohort.cohort_id).order_by(Question.display_order)
        ))
        priorities = []
        nps_sections = []
        likert_sections = []

        for q in questions:
            resps = list(s.scalars(
                select(Response).where(Response.question_id == q.question_id, Response.code_id.in_(eligible_code_ids))
            ))
            if q.type == "ranking":
                rankings = [r.payload.get("order", []) for r in resps]
                all_options = q.payload.get("proposal_slugs", [])
                scores = borda(rankings, all_options=all_options)
                # Normalize to 0-100
                max_score = max(scores.values()) if scores else 0
                bars = [
                    {
                        "slug": slug,
                        "score": score,
                        "normalized": (score / max_score * 100) if max_score else 0,
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
                likert_sections.append({
                    "prompt": q.prompt, "slug": q.slug,
                    "statement": q.payload.get("statement", ""),
                    **likert_histogram(scores),
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

        # Top endorsed comments
        comment_rows = s.execute(
            select(
                Comment.comment_id, Comment.proposal_id, Comment.body,
                func.count(Endorsement.code_id).label("endorsements"),
            )
            .outerjoin(Endorsement, Endorsement.comment_id == Comment.comment_id)
            .where(Comment.hidden_at.is_(None))
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
            "n_respondents": int(n_respondents),
            "priorities": priorities,
            "nps": nps_sections,
            "likert": likert_sections,
            "pledges": pledges,
            "top_comments": top_comments,
        }
