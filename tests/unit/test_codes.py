from ting.codes import generate_code, normalize_code, ALPHABET


def test_alphabet_has_no_confusing_chars():
    for c in "01ILO":
        assert c not in ALPHABET


def test_generate_code_format():
    code = generate_code(prefix="MPE")
    assert code.startswith("MPE-")
    parts = code.split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    for part in (parts[1], parts[2]):
        for ch in part:
            assert ch in ALPHABET


def test_generate_code_no_prefix():
    code = generate_code(prefix=None)
    parts = code.split("-")
    assert len(parts) == 2


def test_normalize_code_strips_and_uppercases():
    assert normalize_code(" mpe-xk7m-n3pq ") == "MPE-XK7M-N3PQ"
    assert normalize_code("mpexk7mn3pq") == "MPEXK7MN3PQ"  # caller decides hyphenation


def test_generate_code_unique_enough():
    seen = {generate_code(prefix="T") for _ in range(1000)}
    assert len(seen) >= 999  # vanishingly rare collision
