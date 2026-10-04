"""Synthetic profile generator.

Produces fabricated newcomers and sponsors so the whole system can run without
any real PII or connection to a DoD system. Deterministic when given a seed, so
tests and demos are reproducible.
"""

from __future__ import annotations

import random

from .matching_service import Newcomer, Sponsor

MOS_CODES = ["11B", "25D", "42A", "68W", "88M", "92Y", "35F", "12B", "31B", "15T"]
FAMILY_STATUSES = ["single", "married", "married_children"]
INTERESTS = [
    "running",
    "gaming",
    "fishing",
    "cooking",
    "weightlifting",
    "photography",
    "hiking",
    "reading",
    "cars",
    "music",
    "coding",
    "soccer",
]
GENDERS = ["F", "M", "X"]  # audit-only field; never scored


def _random_interests(rng: random.Random) -> set[str]:
    return set(rng.sample(INTERESTS, k=rng.randint(1, 4)))


def generate_newcomer(idx: int, rng: random.Random) -> Newcomer:
    return Newcomer(
        member_id=f"N{idx}",
        rank=rng.randint(1, 9),
        mos=rng.choice(MOS_CODES),
        family_status=rng.choice(FAMILY_STATUSES),
        prior_station=rng.random() < 0.25,
        interests=_random_interests(rng),
        efmp=rng.random() < 0.15,
        gender=rng.choice(GENDERS),
    )


def generate_sponsor(idx: int, rng: random.Random) -> Sponsor:
    capacity = rng.randint(1, 3)
    return Sponsor(
        member_id=f"S{idx}",
        rank=rng.randint(2, 9),
        mos=rng.choice(MOS_CODES),
        family_status=rng.choice(FAMILY_STATUSES),
        prior_station=rng.random() < 0.6,
        interests=_random_interests(rng),
        capacity=capacity,
        current_load=rng.randint(0, capacity - 1) if capacity > 1 else 0,
        past_rating=round(rng.uniform(0.4, 1.0), 2),
        efmp_knowledge=rng.random() < 0.4,
        gender=rng.choice(GENDERS),
    )


def generate_cohort(
    n_newcomers: int = 100,
    n_sponsors: int = 600,
    seed: int | None = None,
) -> tuple[list[Newcomer], list[Sponsor]]:
    """Return (newcomers, sponsors). Default scale matches the performance NFR."""
    rng = random.Random(seed)
    newcomers = [generate_newcomer(i, rng) for i in range(1, n_newcomers + 1)]
    sponsors = [generate_sponsor(i, rng) for i in range(1, n_sponsors + 1)]
    return newcomers, sponsors
