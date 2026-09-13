from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import BaseModel, Field
from uuid import UUID
from typing import List, Optional
import numpy as np

app = FastAPI(title="TASP Placement & Matching Gateway", version="1.0.0")

class InboundMatchRequest(BaseModel):
    soldier_id: str = Field(..., max_length=10, example="S10245")
    rank_tier: str = Field(..., example="NCO")
    mos_code: str = Field(..., max_length=4, example="11B")
    gaining_uic: str = Field(..., min_length=6, max_length=8, example="WAAAAA")

class MatchOutputResponse(BaseModel):
    soldier_id: str
    assigned_sponsor_id: Optional[str]
    compatibility_score: float
    status: str

# Heuristic Matrix Configuration Core
WEIGHT_MOS = 0.45
WEIGHT_RANK = 0.40
WEIGHT_LOAD = 0.15

# Simulated Data Store matching indexed relational conditions
MOCK_SPONSOR_POOL = [
    {"sponsor_id": "SP-9901", "rank_tier": "NCO", "mos_code": "11B", "current_uic": "WAAAAA", "active_load": 0},
    {"sponsor_id": "SP-9902", "rank_tier": "NCO", "mos_code": "42A", "current_uic": "WAAAAA", "active_load": 1},
    {"sponsor_id": "SP-9903", "rank_tier": "OFFICER", "mos_code": "11A", "current_uic": "WAAAAA", "active_load": 0}
]

@app.post("/api/v1/pcs/compute-match", response_model=MatchOutputResponse)
async def process_optimal_assignment(payload: InboundMatchRequest):
    """
    Computes candidate closeness matching criteria against open tracking items.
    Prevents assignment errors across critical operational groups.
    """
    best_sponsor_id = None
    highest_affinity = -1.0

    # Execute filtering sequence bounded by identical target UIC destination
    eligible_sponsors = [s for s in MOCK_SPONSOR_POOL if s["current_uic"] == payload.gaining_uic]

    for sponsor in eligible_sponsors:
        # 1. Structural Identity MOS Match Verification
        mos_score = 1.0 if sponsor["mos_code"] == payload.mos_code else 0.0
        
        # 2. Command Tier Rank Alignment Boundary Check
        rank_score = 1.0 if sponsor["rank_tier"] == payload.rank_tier else 0.0
        
        # 3. Workload Mitigation Buffer
        load_score = max(0.0, 1.0 - (sponsor["active_load"] * 0.33))

        # Core Matrix Compounding Equation
        composite_score = (
            (mos_score * WEIGHT_MOS) + 
            (rank_score * WEIGHT_RANK) + 
            (load_score * WEIGHT_LOAD)
        )

        if composite_score > highest_affinity:
            highest_affinity = composite_score
            best_sponsor_id = sponsor["sponsor_id"]

    # Enforce quality gating threshold minimum requirement
    if best_sponsor_id and highest_affinity >= 0.50:
        return {
            "soldier_id": payload.soldier_id,
            "assigned_sponsor_id": best_sponsor_id,
            "compatibility_score": round(float(highest_affinity), 2),
            "status": "COMPUTED_MATCH"
        }

    return {
        "soldier_id": payload.soldier_id,
        "assigned_sponsor_id": None,
        "compatibility_score": 0.0,
        "status": "UNASSIGNED"
    }
