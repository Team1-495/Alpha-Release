"""Legacy v1 matching endpoint — retained for lineage, deprecated.

This is the Alpha release's original single-sponsor greedy matcher, preserved
(aside from packaging) so the evolution from the Alpha heuristic to the v2
cohort-wide optimizer is visible in one codebase. It keeps the Alpha's original
terminology (``soldier_id``, ``rank_tier``, ``gaining_uic``) and its in-module
mock sponsor pool, and it does not touch the v2 store.

New code should use ``POST /v1/match`` (see ``main.py``). This route is marked
``deprecated=True`` so it renders struck-through in the OpenAPI docs, and it
will be removed once all clients migrate.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["legacy-v1-deprecated"])


class InboundMatchRequest(BaseModel):
    soldier_id: str = Field(..., max_length=10, examples=["S10245"])
    rank_tier: str = Field(..., examples=["NCO"])
    mos_code: str = Field(..., max_length=4, examples=["11B"])
    gaining_uic: str = Field(..., min_length=6, max_length=8, examples=["WAAAAA"])


class MatchOutputResponse(BaseModel):
    soldier_id: str
    assigned_sponsor_id: str | None
    compatibility_score: float
    status: str


# Original Alpha heuristic weights (MOS / rank tier / workload).
WEIGHT_MOS = 0.45
WEIGHT_RANK = 0.40
WEIGHT_LOAD = 0.15

# Original Alpha in-module mock sponsor pool.
MOCK_SPONSOR_POOL = [
    {"sponsor_id": "SP-9901", "rank_tier": "NCO", "mos_code": "11B",
     "current_uic": "WAAAAA", "active_load": 0},
    {"sponsor_id": "SP-9902", "rank_tier": "NCO", "mos_code": "42A",
     "current_uic": "WAAAAA", "active_load": 1},
    {"sponsor_id": "SP-9903", "rank_tier": "OFFICER", "mos_code": "11A",
     "current_uic": "WAAAAA", "active_load": 0},
]


@router.post(
    "/api/v1/pcs/compute-match",
    response_model=MatchOutputResponse,
    deprecated=True,
    summary="[Deprecated v1] Single-sponsor greedy match — superseded by POST /v1/match",
)
async def process_optimal_assignment(payload: InboundMatchRequest) -> MatchOutputResponse:
    """Alpha-release heuristic: pick the single best sponsor in the gaining UIC by a
    weighted MOS/rank/load score. Superseded by the v2 cohort-wide optimizer, which
    assigns the whole incoming cohort at once under capacity and eligibility constraints.
    """
    best_sponsor_id: str | None = None
    highest_affinity = -1.0

    eligible = [s for s in MOCK_SPONSOR_POOL if s["current_uic"] == payload.gaining_uic]
    for sponsor in eligible:
        mos_score = 1.0 if sponsor["mos_code"] == payload.mos_code else 0.0
        rank_score = 1.0 if sponsor["rank_tier"] == payload.rank_tier else 0.0
        load_score = max(0.0, 1.0 - (sponsor["active_load"] * 0.33))
        composite = mos_score * WEIGHT_MOS + rank_score * WEIGHT_RANK + load_score * WEIGHT_LOAD
        if composite > highest_affinity:
            highest_affinity = composite
            best_sponsor_id = sponsor["sponsor_id"]

    if best_sponsor_id and highest_affinity >= 0.50:
        return MatchOutputResponse(
            soldier_id=payload.soldier_id,
            assigned_sponsor_id=best_sponsor_id,
            compatibility_score=round(float(highest_affinity), 2),
            status="COMPUTED_MATCH",
        )

    return MatchOutputResponse(
        soldier_id=payload.soldier_id,
        assigned_sponsor_id=None,
        compatibility_score=0.0,
        status="UNASSIGNED",
    )
