import csv
import io
from datetime import UTC, datetime
from pathlib import Path

import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape
from qrcode.image.svg import SvgImage
from sqlalchemy import select, update

from ..codes import generate_code
from ..db import session_scope
from ..models import Code, Cohort


def generate_codes(*, cohort_name: str, count: int) -> list[str]:
    """Generate ``count`` unique access codes for the named cohort.

    The code prefix is derived from the cohort's school_code + batch_number,
    e.g. school_code="MPE", batch_number=1 → prefix "MPE01".
    """
    out: list[str] = []
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            raise ValueError(f"unknown cohort: {cohort_name}")
        prefix = f"{cohort.school_code}{cohort.batch_number:02d}"
        # Load the full set of existing code_strs into memory for collision
        # checks. Fine through ~100k codes (the unique constraint on Code.code_str
        # would catch a collision at insert time anyway); revisit if a single
        # ting instance ever needs to scale past that.
        existing = {row[0] for row in s.execute(select(Code.code_str)).all()}
        while len(out) < count:
            code_str = generate_code(prefix=prefix)
            if code_str in existing:
                continue
            existing.add(code_str)
            s.add(Code(code_str=code_str, cohort_id=cohort.cohort_id))
            out.append(code_str)
    return out


def list_codes(*, cohort_name: str, only_unprinted: bool = False) -> list[Code]:
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            return []
        q = select(Code).where(Code.cohort_id == cohort.cohort_id)
        if only_unprinted:
            q = q.where(Code.printed_at.is_(None))
        rows = list(s.scalars(q))
        s.expunge_all()
        return rows


def mark_printed(*, code_strs: list[str]) -> int:
    with session_scope() as s:
        result = s.execute(
            update(Code).where(Code.code_str.in_(code_strs)).values(printed_at=datetime.now(UTC))
        )
        return result.rowcount or 0


def retire_cohort(*, cohort_name: str) -> None:
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            raise ValueError(f"unknown cohort: {cohort_name}")
        cohort.retired_at = datetime.now(UTC)


def export_csv(*, codes: list[Code]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["code_str"])
    for c in codes:
        w.writerow([c.code_str])
    return buf.getvalue()


def _qr_svg(data: str, box_size: int = 4) -> str:
    qr = qrcode.QRCode(box_size=box_size, border=1, image_factory=SvgImage)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def export_html(*, codes: list[Code], base_url: str) -> str:
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=select_autoescape())
    tpl = env.get_template("admin/code_export.html")
    items = [
        {
            "code_str": c.code_str,
            "url": f"{base_url.rstrip('/')}/r/{c.code_str}?src=qr",
            "qr_svg": _qr_svg(f"{base_url.rstrip('/')}/r/{c.code_str}?src=qr"),
        }
        for c in codes
    ]
    return tpl.render(items=items, base_url=base_url)
