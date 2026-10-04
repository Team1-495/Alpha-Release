"""Unit tests for the compatibility scorer."""

from dataclasses import replace

from app.matching_service import (
    FEATURE_WEIGHTS,
    Newcomer,
    Sponsor,
    compatibility_score,
    explain,
    feature_breakdown,
)


def _newcomer(**kw) -> Newcomer:
    base = dict(
        member_id="N1",
        rank=5,
        mos="11B",
        family_status="married",
        prior_station=True,
        interests={"running", "gaming"},
        efmp=False,
        gender="F",
    )
    base.update(kw)
    return Newcomer(**base)


def _sponsor(**kw) -> Sponsor:
    base = dict(
        member_id="S1",
        rank=5,
        mos="11B",
        family_status="married",
        prior_station=True,
        interests={"running", "gaming"},
        capacity=2,
        current_load=0,
        past_rating=1.0,
        efmp_knowledge=True,
        gender="M",
    )
    base.update(kw)
    return Sponsor(**base)


def test_weights_sum_to_one():
    assert abs(sum(FEATURE_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_in_unit_interval():
    assert 0.0 <= compatibility_score(_newcomer(), _sponsor()) <= 1.0


def test_perfect_pair_scores_top():
    # Same MOS, same rank, same family, identical interests, perfect rating,
    # sponsor knows the station -> score should be 1.0.
    assert compatibility_score(_newcomer(), _sponsor()) == 1.0


def test_mismatch_scores_lower_than_match():
    good = compatibility_score(_newcomer(), _sponsor())
    bad = compatibility_score(
        _newcomer(),
        _sponsor(
            mos="92Y",
            rank=1,
            family_status="single",
            interests=set(),
            past_rating=0.4,
            prior_station=False,
        ),
    )
    assert bad < good


def test_same_mos_feature_binary():
    assert feature_breakdown(_newcomer(), _sponsor())["same_mos"] == 1.0
    assert feature_breakdown(_newcomer(), _sponsor(mos="25D"))["same_mos"] == 0.0


def test_rank_proximity_decays_with_gap():
    close = feature_breakdown(_newcomer(rank=5), _sponsor(rank=6))["rank_proximity"]
    far = feature_breakdown(_newcomer(rank=5), _sponsor(rank=9))["rank_proximity"]
    assert close > far


def test_gender_is_never_scored():
    """Fairness: changing a protected attribute must not change the score."""
    base_nc, base_sp = _newcomer(gender="F"), _sponsor(gender="M")
    base_score = compatibility_score(base_nc, base_sp)
    for g_nc in ("F", "M", "X", None):
        for g_sp in ("F", "M", "X", None):
            nc = replace(base_nc, gender=g_nc)
            sp = replace(base_sp, gender=g_sp)
            assert compatibility_score(nc, sp) == base_score


def test_explanations_are_human_readable():
    reasons = explain(_newcomer(), _sponsor())
    assert reasons
    assert any("job specialty" in r for r in reasons)
    assert all(isinstance(r, str) for r in reasons)
