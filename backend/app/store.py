"""In-memory data store.

Stands in for PostgreSQL during local dev, tests, and CI so the Alpha runs with
no database service. The schema in db/schema.sql is the canonical production
store; this module mirrors just enough of it to drive the API. Swapping in a
real database means replacing this module's internals, not the API.
"""

from __future__ import annotations

from .matching_service import MatchResult, Newcomer, Sponsor
from .synthetic_data import generate_cohort


class Store:
    def __init__(self) -> None:
        self.newcomers: dict[str, Newcomer] = {}
        self.sponsors: dict[str, Sponsor] = {}
        # newcomer_id -> {"sponsor_id": str, "status": str}
        self.approved: dict[str, dict[str, str]] = {}
        # last generated recommendations, newcomer_id -> MatchResult
        self.last_results: dict[str, MatchResult] = {}

    def seed_synthetic(self, n_newcomers: int = 30, n_sponsors: int = 80, seed: int = 42) -> None:
        newcomers, sponsors = generate_cohort(n_newcomers, n_sponsors, seed=seed)
        self.newcomers = {n.member_id: n for n in newcomers}
        self.sponsors = {s.member_id: s for s in sponsors}
        self.approved.clear()
        self.last_results.clear()

    def cohort(self) -> tuple[list[Newcomer], list[Sponsor]]:
        return list(self.newcomers.values()), list(self.sponsors.values())


# Process-wide store instance used by the API.
store = Store()
