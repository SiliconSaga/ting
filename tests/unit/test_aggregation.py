from ting.aggregation import borda, likert_histogram, nps


def test_borda_full_ranking():
    # 3 voters, 3 proposals. Voter1: [A,B,C], Voter2: [A,C,B], Voter3: [B,A,C].
    rankings = [["A", "B", "C"], ["A", "C", "B"], ["B", "A", "C"]]
    scores = borda(rankings)
    # 3-place ranking: 1st=2pts, 2nd=1pt, 3rd=0pts
    # A: 2+2+1 = 5; B: 1+0+2 = 3; C: 0+1+0 = 1
    assert scores == {"A": 5, "B": 3, "C": 1}


def test_borda_top_n_partial():
    # Top-2: voters submit a subset. Unranked items get 0.
    rankings = [["A", "B"], ["A", "C"], ["B", "A"]]
    scores = borda(rankings, all_options=["A", "B", "C", "D"])
    # 4-option Borda: 1st=3, 2nd=2, others=0
    # A: 3+3+2 = 8; B: 2+0+3 = 5; C: 0+2+0 = 2; D: 0
    assert scores == {"A": 8, "B": 5, "C": 2, "D": 0}


def test_nps():
    scores = [0, 6, 7, 8, 9, 10, 10]
    # detractors 0,6 -> 2/7 ~ 28.6%; promoters 9,10,10 -> 3/7 ~ 42.9%; nps ~ +14
    r = nps(scores)
    assert r["n"] == 7
    assert r["detractors"] == 2
    assert r["passives"] == 2
    assert r["promoters"] == 3
    assert -100 <= r["nps"] <= 100
    assert abs(r["nps"] - (3 - 2) / 7 * 100) < 0.5


def test_likert_histogram():
    scores = [1, 2, 2, 3, 4, 4, 4, 5]
    h = likert_histogram(scores)
    assert h["counts"] == {1: 1, 2: 2, 3: 1, 4: 3, 5: 1}
    assert abs(h["mean"] - sum(scores)/len(scores)) < 1e-6
    assert h["agree_pct"] == 50.0  # 4 of 8 are score>=4 -> 50%
