"""Top-3 hit-rate evaluation.

This is the match-quality non-functional requirement: on a held-out synthetic
set, a known-good sponsor should appear in the top-3 for at least 70% of
newcomers. This is a ranking metric (top-3 hit rate), not classification
accuracy.

To create ground truth without a labeled outcome set, we plant one clearly
ideal sponsor per newcomer (identical MOS, rank, family, interests, top rating,
station knowledge) inside a large pool of random distractors, then check how
often that planted sponsor lands in the top-3.
"""

import random

from app.matching_service import Newcomer, Sponsor, match_cohort
from app.synthetic_data import INTERESTS, MOS_CODES, generate_sponsor


def _build_eval_set(n=50, distractors=200, seed=99):
    rng = random.Random(seed)
    newcomers: list[Newcomer] = []
    sponsors: list[Sponsor] = []
    known_good: dict[str, str] = {}

    for i in range(1, n + 1):
        rank = rng.randint(1, 9)
        mos = rng.choice(MOS_CODES)
        family = rng.choice(["single", "married", "married_children"])
        interests = set(rng.sample(INTERESTS, k=3))
        nc = Newcomer(
            member_id=f"N{i}",
            rank=rank,
            mos=mos,
            family_status=family,
            prior_station=False,
            interests=interests,
            efmp=False,
        )
        # The planted ideal sponsor mirrors the newcomer on every scored feature,
        # has plenty of capacity, a perfect rating, and knows the station.
        good = Sponsor(
            member_id=f"GOOD{i}",
            rank=rank,
            mos=mos,
            family_status=family,
            prior_station=True,
            interests=set(interests),
            capacity=5,
            current_load=0,
            past_rating=1.0,
            efmp_knowledge=True,
        )
        newcomers.append(nc)
        sponsors.append(good)
        known_good[nc.member_id] = good.member_id

    # Random distractors with capacity, drawn from the standard generator.
    for j in range(1, distractors + 1):
        sponsors.append(generate_sponsor(10_000 + j, rng))

    rng.shuffle(sponsors)
    return newcomers, sponsors, known_good


def test_top3_hit_rate_at_least_70pct():
    newcomers, sponsors, known_good = _build_eval_set()
    results = match_cohort(newcomers, sponsors, top_k=3)

    hits = 0
    for r in results:
        top_ids = {rec.sponsor_id for rec in r.recommendations}
        if known_good[r.newcomer_id] in top_ids:
            hits += 1

    hit_rate = hits / len(results)
    assert hit_rate >= 0.70, f"top-3 hit rate {hit_rate:.0%} below 70% target"
