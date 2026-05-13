import secrets

# Crockford-style no-confusion alphabet: excludes 0, 1, I, L, O
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_code(prefix: str | None = "MPE", segment_len: int = 4, segments: int = 2) -> str:
    if segment_len <= 0 or segments <= 0:
        raise ValueError(
            f"segment_len and segments must be positive (got {segment_len}, {segments})"
        )
    parts = ["".join(secrets.choice(ALPHABET) for _ in range(segment_len)) for _ in range(segments)]
    if prefix:
        return f"{prefix}-{'-'.join(parts)}"
    return "-".join(parts)


def normalize_code(raw: str) -> str:
    return raw.strip().upper()
