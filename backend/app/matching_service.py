"""UNITE compatibility matching — the AI feature.

Two-stage pipeline (see README section 5):

  Stage 1  Compatibility scoring. For every (newcomer, sponsor) pair, a
           transparent content-based scorer produces a value in [0, 1]. It is a
           weighted sum over comparable features and needs no training data.

  Stage 2  Constrained assignment. Sponsors are assigned across the whole
           incoming cohort to maximise total compatibility, subject to hard
           constraints (sponsor capacity, EFMP eligibility). Solved as an
           assignment problem with scipy's linear_sum_assignment.

This module depends only on the standard library, NumPy and SciPy, so it runs
standalone on synthetic data without a database or web server (see the
`__main__` block at the bottom).

Protected attributes (gender, race, sexual orientation, ethnicity) are never
read by the scorer. They are not parameters of any function here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

# --------------------------------------------------------------------------- #
# Feature weights. They sum to 1.0, so a perfect score across every feature is
# exactly 1.0 and the composite score is always in [0, 1].
# --------------------------------------------------------------------------- #
FEATURE_WEIGHTS: dict[str, float] = {
    "same_mos": 0.30,
    "rank_proximity": 0.20,
    "family_match": 0.15,
    "shared_interests": 0.15,
    "sponsor_track_record": 0.10,
    "prior_station_match": 0.10,
}

# Pay-grade gap at which rank proximity decays to 0.
MAX_RANK_GAP = 6

# A pair that violates a hard constraint gets this cost in the optimiser so it
# is never chosen unless nothing else is available.
_INELIGIBLE_COST = 1e6

# Threshold above which a feature is worth mentioning in a human-readable reason.
_REASON_THRESHOLD = 0.5


@dataclass
class Newcomer:
    """An incoming service member who needs a sponsor."""

    member_id: str
    rank: int  # pay-grade as an integer
    mos: str  # job specialty code
    family_status: str  # "single" | "married" | "married_children"
    prior_station: bool  # has served at this installation before
    interests: set[str] = field(default_factory=set)
    efmp: bool = False  # needs an EFMP-knowledgeable sponsor
    # Audit only — deliberately never read by the scorer.
    gender: str | None = None


@dataclass
class Sponsor:
    """A service member available to sponsor newcomers this cycle."""

    member_id: str
    rank: int
    mos: str
    family_status: str
    prior_station: bool
    interests: set[str] = field(default_factory=set)
    capacity: int = 1  # max newcomers this sponsor can take
    current_load: int = 0  # already assigned this cycle
    past_rating: float = 0.5  # historical survey score in [0, 1]
    efmp_knowledge: bool = False
    gender: str | None = None  # audit only

    @property
    def remaining_capacity(self) -> int:
        return max(0, self.capacity - self.current_load)


# Family situations that are partially compatible even when not identical.
_FAMILY_PARTIAL = {
    frozenset({"married", "married_children"}): 0.6,
    frozenset({"single", "married"}): 0.3,
    frozenset({"single", "married_children"}): 0.2,
}


def _family_score(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return _FAMILY_PARTIAL.get(frozenset({a, b}), 0.0)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def is_eligible(newcomer: Newcomer, sponsor: Sponsor) -> bool:
    """Hard eligibility gate. A newcomer flagged EFMP may only be paired with a
    sponsor who has EFMP knowledge. Capacity is handled by the optimiser."""
    if newcomer.efmp and not sponsor.efmp_knowledge:
        return False
    return True


def feature_breakdown(newcomer: Newcomer, sponsor: Sponsor) -> dict[str, float]:
    """Per-feature scores in [0, 1] for one pair. Used for both scoring and for
    generating explanations. Note: `gender` is never referenced."""
    rank_gap = abs(newcomer.rank - sponsor.rank)
    return {
        "same_mos": 1.0 if newcomer.mos == sponsor.mos else 0.0,
        "rank_proximity": max(0.0, 1.0 - rank_gap / MAX_RANK_GAP),
        "family_match": _family_score(newcomer.family_status, sponsor.family_status),
        "shared_interests": _jaccard(newcomer.interests, sponsor.interests),
        "sponsor_track_record": float(np.clip(sponsor.past_rating, 0.0, 1.0)),
        "prior_station_match": 1.0 if sponsor.prior_station else 0.0,
    }


def compatibility_score(newcomer: Newcomer, sponsor: Sponsor) -> float:
    """Composite compatibility in [0, 1] for a single pair."""
    parts = feature_breakdown(newcomer, sponsor)
    return float(sum(FEATURE_WEIGHTS[k] * v for k, v in parts.items()))


def explain(newcomer: Newcomer, sponsor: Sponsor) -> list[str]:
    """Plain-language reasons a pairing is a good match, strongest first."""
    parts = feature_breakdown(newcomer, sponsor)
    ranked = sorted(
        parts.items(), key=lambda kv: FEATURE_WEIGHTS[kv[0]] * kv[1], reverse=True
    )
    reasons: list[str] = []
    for name, value in ranked:
        if value < _REASON_THRESHOLD:
            continue
        if name == "same_mos":
            reasons.append("same job specialty (MOS)")
        elif name == "rank_proximity":
            reasons.append("close in rank")
        elif name == "family_match":
            reasons.append("similar family situation")
        elif name == "shared_interests":
            shared = sorted(newcomer.interests & sponsor.interests)
            if shared:
                reasons.append("shared interests: " + ", ".join(shared[:3]))
        elif name == "sponsor_track_record":
            reasons.append("strong sponsor track record")
        elif name == "prior_station_match":
            reasons.append("familiar with this installation")
    if newcomer.efmp and sponsor.efmp_knowledge:
        reasons.append("EFMP-knowledgeable")
    return reasons[:3] if reasons else ["best available compatibility"]


def score_matrix(newcomers: list[Newcomer], sponsors: list[Sponsor]) -> np.ndarray:
    """N x M matrix of composite scores. Vectorised for performance.

    Ineligible pairs are set to NaN so callers can mask them out.
    """
    n, m = len(newcomers), len(sponsors)
    scores = np.zeros((n, m), dtype=float)
    # Precompute sponsor-only quantities once.
    spons_rank = np.array([s.rank for s in sponsors])
    spons_rating = np.clip(np.array([s.past_rating for s in sponsors]), 0.0, 1.0)
    spons_prior = np.array([1.0 if s.prior_station else 0.0 for s in sponsors])

    for i, nc in enumerate(newcomers):
        same_mos = np.array([1.0 if nc.mos == s.mos else 0.0 for s in sponsors])
        rank_prox = np.maximum(0.0, 1.0 - np.abs(nc.rank - spons_rank) / MAX_RANK_GAP)
        family = np.array(
            [_family_score(nc.family_status, s.family_status) for s in sponsors]
        )
        interests = np.array([_jaccard(nc.interests, s.interests) for s in sponsors])
        row = (
            FEATURE_WEIGHTS["same_mos"] * same_mos
            + FEATURE_WEIGHTS["rank_proximity"] * rank_prox
            + FEATURE_WEIGHTS["family_match"] * family
            + FEATURE_WEIGHTS["shared_interests"] * interests
            + FEATURE_WEIGHTS["sponsor_track_record"] * spons_rating
            + FEATURE_WEIGHTS["prior_station_match"] * spons_prior
        )
        # Mask ineligible pairs.
        for j, s in enumerate(sponsors):
            if not is_eligible(nc, s):
                row[j] = np.nan
        scores[i] = row
    return scores


@dataclass
class Recommendation:
    sponsor_id: str
    score: float
    reasons: list[str]


@dataclass
class MatchResult:
    newcomer_id: str
    recommendations: list[Recommendation]  # ranked top-k
    assigned_sponsor_id: str | None  # optimiser's capacity-aware pick
    unmatched: bool


def _optimal_assignment(
    newcomers: list[Newcomer],
    sponsors: list[Sponsor],
    scores: np.ndarray,
) -> dict[int, int | None]:
    """Globally optimal sponsor assignment respecting remaining capacity.

    Each sponsor is expanded into one column per open slot. Newcomers that
    cannot be seated (demand > capacity, or no eligible sponsor) map to None.
    Returns {newcomer_index: sponsor_index or None}.
    """
    n = len(newcomers)
    # Expand sponsors by remaining capacity.
    slot_to_sponsor: list[int] = []
    for j, s in enumerate(sponsors):
        slot_to_sponsor.extend([j] * s.remaining_capacity)
    num_slots = len(slot_to_sponsor)

    if num_slots == 0:
        return {i: None for i in range(n)}

    # Cost matrix: rows = newcomers, cols = slots. Pad with dummy columns so the
    # problem is always solvable; assignment to a dummy means "unmatched".
    width = max(num_slots, n)
    cost = np.full((n, width), _INELIGIBLE_COST, dtype=float)
    for col, j in enumerate(slot_to_sponsor):
        for i in range(n):
            s = scores[i, j]
            cost[i, col] = _INELIGIBLE_COST if np.isnan(s) else (1.0 - s)

    rows, cols = linear_sum_assignment(cost)
    assignment: dict[int, int | None] = {i: None for i in range(n)}
    for i, col in zip(rows, cols, strict=False):
        if col < num_slots and cost[i, col] < _INELIGIBLE_COST:
            assignment[i] = slot_to_sponsor[col]
    return assignment


def match_cohort(
    newcomers: list[Newcomer],
    sponsors: list[Sponsor],
    top_k: int = 3,
) -> list[MatchResult]:
    """Run the full two-stage pipeline for a cohort.

    Returns, per newcomer, a ranked top-k of eligible sponsors (each with a
    score and reasons) plus the optimiser's capacity-aware assigned sponsor.
    """
    if not newcomers:
        return []
    if not sponsors:
        return [
            MatchResult(nc.member_id, [], None, unmatched=True) for nc in newcomers
        ]

    scores = score_matrix(newcomers, sponsors)
    assignment = _optimal_assignment(newcomers, sponsors, scores)

    results: list[MatchResult] = []
    for i, nc in enumerate(newcomers):
        row = scores[i]
        eligible = [j for j in range(len(sponsors)) if not np.isnan(row[j])]
        eligible.sort(key=lambda j: row[j], reverse=True)
        top = eligible[:top_k]

        recs = [
            Recommendation(
                sponsor_id=sponsors[j].member_id,
                score=round(float(row[j]), 4),
                reasons=explain(nc, sponsors[j]),
            )
            for j in top
        ]
        assigned_idx = assignment.get(i)
        assigned_id = sponsors[assigned_idx].member_id if assigned_idx is not None else None
        results.append(
            MatchResult(
                newcomer_id=nc.member_id,
                recommendations=recs,
                assigned_sponsor_id=assigned_id,
                unmatched=assigned_id is None,
            )
        )
    return results


if __name__ == "__main__":
    # Standalone demo on synthetic data. Run with:  python -m app.matching_service
    from app.synthetic_data import generate_cohort

    ncs, spons = generate_cohort(n_newcomers=8, n_sponsors=20, seed=7)
    print("Recommended matches (for coordinator approval):")
    for r in match_cohort(ncs, spons):
        if r.unmatched:
            print(f"  {r.newcomer_id} -> UNMATCHED (demand exceeded capacity)")
            continue
        top = r.recommendations[0]
        print(
            f"  {r.newcomer_id} -> {r.assigned_sponsor_id}  "
            f"score={top.score:.2f}  because: {', '.join(top.reasons)}"
        )
