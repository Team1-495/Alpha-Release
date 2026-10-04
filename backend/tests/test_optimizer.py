"""Tests for the constrained assignment optimizer."""

import time
from collections import Counter

from app.matching_service import Newcomer, Sponsor, match_cohort
from app.synthetic_data import generate_cohort


def _nc(i, **kw) -> Newcomer:
    base = dict(
        member_id=f"N{i}",
        rank=5,
        mos="11B",
        family_status="single",
        prior_station=False,
        interests=set(),
        efmp=False,
    )
    base.update(kw)
    return Newcomer(**base)


def _sp(i, **kw) -> Sponsor:
    base = dict(
        member_id=f"S{i}",
        rank=5,
        mos="11B",
        family_status="single",
        prior_station=False,
        interests=set(),
        capacity=1,
        current_load=0,
        past_rating=0.8,
        efmp_knowledge=False,
    )
    base.update(kw)
    return Sponsor(**base)


def test_capacity_never_exceeded():
    newcomers = [_nc(i) for i in range(6)]
    sponsors = [_sp(1, capacity=2), _sp(2, capacity=2), _sp(3, capacity=2)]
    results = match_cohort(newcomers, sponsors)
    counts = Counter(r.assigned_sponsor_id for r in results if r.assigned_sponsor_id)
    for sid, used in counts.items():
        cap = next(s.capacity for s in sponsors if s.member_id == sid)
        assert used <= cap


def test_current_load_reduces_available_capacity():
    # One sponsor, capacity 2 but already carrying 2 -> no open slots.
    newcomers = [_nc(1)]
    sponsors = [_sp(1, capacity=2, current_load=2)]
    results = match_cohort(newcomers, sponsors)
    assert results[0].unmatched is True


def test_efmp_only_assigned_to_knowledgeable_sponsor():
    newcomers = [_nc(1, efmp=True)]
    sponsors = [_sp(1, efmp_knowledge=False), _sp(2, efmp_knowledge=True)]
    results = match_cohort(newcomers, sponsors)
    assert results[0].assigned_sponsor_id == "S2"
    # The ineligible sponsor should not appear in recommendations either.
    rec_ids = {r.sponsor_id for r in results[0].recommendations}
    assert "S1" not in rec_ids


def test_efmp_newcomer_unmatched_when_no_knowledgeable_sponsor():
    newcomers = [_nc(1, efmp=True)]
    sponsors = [_sp(1, efmp_knowledge=False)]
    results = match_cohort(newcomers, sponsors)
    assert results[0].unmatched is True
    assert results[0].assigned_sponsor_id is None


def test_demand_exceeds_capacity_returns_unmatched():
    newcomers = [_nc(i) for i in range(3)]
    sponsors = [_sp(1, capacity=1)]
    results = match_cohort(newcomers, sponsors)
    unmatched = [r for r in results if r.unmatched]
    assert len(unmatched) == 2  # only one can be seated


def test_top_k_length():
    newcomers = [_nc(1)]
    sponsors = [_sp(i) for i in range(1, 6)]
    results = match_cohort(newcomers, sponsors, top_k=3)
    assert len(results[0].recommendations) == 3
    # Recommendations are sorted by score, descending.
    scores = [r.score for r in results[0].recommendations]
    assert scores == sorted(scores, reverse=True)


def test_performance_100_by_600_under_3s():
    """Non-functional requirement: top-3 for ~100 newcomers vs ~600 sponsors
    in under 3 seconds. Uses a generous 3s bound; typical runtime is well below."""
    newcomers, sponsors = generate_cohort(n_newcomers=100, n_sponsors=600, seed=1)
    start = time.perf_counter()
    results = match_cohort(newcomers, sponsors, top_k=3)
    elapsed = time.perf_counter() - start
    assert len(results) == 100
    assert elapsed < 3.0, f"matching took {elapsed:.2f}s (budget 3.0s)"
