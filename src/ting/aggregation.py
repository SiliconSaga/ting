from collections.abc import Iterable, Sequence


def borda(rankings: Iterable[Sequence[str]], all_options: Sequence[str] | None = None) -> dict[str, int]:
    """Borda count. Each voter's ranking is an ordered list.

    If all_options is provided, points are based on that universe (top-N ballots assume
    unranked items at zero). If not provided, derives the universe from the union of
    voters' ballots — appropriate for full-rank ballots.
    """
    rankings_l = [list(r) for r in rankings]
    universe = list(all_options) if all_options is not None else sorted({x for r in rankings_l for x in r})
    n_opts = len(universe)
    scores: dict[str, int] = {opt: 0 for opt in universe}
    for ballot in rankings_l:
        for idx, choice in enumerate(ballot):
            if choice in scores:
                scores[choice] += max(0, n_opts - 1 - idx)
    return scores


def nps(scores: Sequence[int]) -> dict[str, float | int]:
    n = len(scores)
    if n == 0:
        return {"n": 0, "detractors": 0, "passives": 0, "promoters": 0, "nps": 0.0}
    detractors = sum(1 for s in scores if 0 <= s <= 6)
    passives = sum(1 for s in scores if 7 <= s <= 8)
    promoters = sum(1 for s in scores if 9 <= s <= 10)
    nps_val = (promoters - detractors) / n * 100
    return {"n": n, "detractors": detractors, "passives": passives, "promoters": promoters, "nps": nps_val}


def likert_histogram(scores: Sequence[int]) -> dict[str, object]:
    counts = {i: 0 for i in range(1, 6)}
    for s in scores:
        if 1 <= s <= 5:
            counts[s] += 1
    n = sum(counts.values())
    mean = sum(k * v for k, v in counts.items()) / n if n else 0.0
    agree = counts[4] + counts[5]
    return {
        "counts": counts,
        "n": n,
        "mean": mean,
        "agree_pct": (agree / n * 100) if n else 0.0,
    }
