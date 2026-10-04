"""UNITE FastAPI backend.

Every request the dashboard makes goes through here. The matching service is the
AI feature; this layer authenticates, serves profiles, runs matches, and records
coordinator approvals. The matching service never writes a final assignment
itself — a human approves through /v1/matches/{id}/approve.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from . import auth, legacy
from .matching_service import match_cohort
from .models import (
    ApprovedMatchModel,
    ApproveRequest,
    LoginRequest,
    LoginResponse,
    MatchRequest,
    MatchResultModel,
    NewcomerModel,
)
from .store import store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not store.newcomers:
        store.seed_synthetic()
    yield


app = FastAPI(title="UNITE — Sponsor Matching", version="0.1.0", lifespan=lifespan)

# The dashboard is served separately in dev, so allow it to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy v1 route (Alpha-release heuristic), preserved for lineage and
# marked deprecated in the OpenAPI docs. See backend/app/legacy.py.
app.include_router(legacy.router)


def require_role(*allowed: str):
    """Dependency: reject requests without a valid bearer token in an allowed role."""

    def _dep(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        token = authorization.split(" ", 1)[1]
        role = auth.role_for_token(token)
        if role is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        if allowed and role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return role

    return _dep


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/auth/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    token = auth.authenticate(req.username, req.password)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    role = auth.role_for_token(token)
    assert role is not None
    return LoginResponse(token=token, role=role)


@app.get("/v1/newcomers", response_model=list[NewcomerModel])
def list_newcomers() -> list[NewcomerModel]:
    return [
        NewcomerModel(
            member_id=n.member_id,
            rank=n.rank,
            mos=n.mos,
            family_status=n.family_status,
            prior_station=n.prior_station,
            interests=sorted(n.interests),
            efmp=n.efmp,
            gender=n.gender,
        )
        for n in store.newcomers.values()
    ]


@app.post("/v1/match", response_model=list[MatchResultModel])
def run_match(req: MatchRequest) -> list[MatchResultModel]:
    if req.newcomers or req.sponsors:
        newcomers = [n.to_newcomer() for n in req.newcomers]
        sponsors = [s.to_sponsor() for s in req.sponsors]
    else:
        newcomers, sponsors = store.cohort()

    results = match_cohort(newcomers, sponsors, top_k=req.top_k)
    store.last_results = {r.newcomer_id: r for r in results}

    return [
        MatchResultModel(
            newcomer_id=r.newcomer_id,
            recommendations=[
                {"sponsor_id": rec.sponsor_id, "score": rec.score, "reasons": rec.reasons}
                for rec in r.recommendations
            ],
            assigned_sponsor_id=r.assigned_sponsor_id,
            unmatched=r.unmatched,
        )
        for r in results
    ]


@app.post("/v1/matches/{newcomer_id}/approve", response_model=ApprovedMatchModel)
def approve_match(
    newcomer_id: str,
    req: ApproveRequest,
    _role: str = Depends(require_role("coordinator", "admin")),
) -> ApprovedMatchModel:
    result = store.last_results.get(newcomer_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run a match for this newcomer first")

    recommended_ids = {rec.sponsor_id for rec in result.recommendations}
    is_override = req.override or req.sponsor_id not in recommended_ids
    status_label = "override" if is_override else "approved"

    store.approved[newcomer_id] = {"sponsor_id": req.sponsor_id, "status": status_label}
    return ApprovedMatchModel(
        newcomer_id=newcomer_id, sponsor_id=req.sponsor_id, status=status_label
    )


@app.get("/v1/matches", response_model=list[ApprovedMatchModel])
def list_matches() -> list[ApprovedMatchModel]:
    return [
        ApprovedMatchModel(newcomer_id=nc, sponsor_id=v["sponsor_id"], status=v["status"])
        for nc, v in store.approved.items()
    ]
