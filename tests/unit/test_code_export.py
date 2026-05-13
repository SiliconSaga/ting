from ting.services.code_service import export_csv, export_html


class _C:
    def __init__(self, s): self.code_str = s


def test_export_csv():
    text = export_csv(codes=[_C("A"), _C("B")])
    assert "code_str" in text
    assert "A" in text and "B" in text


def test_export_html_contains_url_and_code():
    html = export_html(codes=[_C("MPE-XK7M-N3PQ")], base_url="https://ting.cmdbee.org")
    assert "MPE-XK7M-N3PQ" in html
    assert "ting.cmdbee.org/r/MPE-XK7M-N3PQ" in html
    assert "<svg" in html  # QR rendered as inline SVG
