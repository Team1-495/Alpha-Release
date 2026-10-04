"""Pydantic models for the HTTP API.

These are the wire formats. Internal matching uses the dataclasses in
matching_service; `to_newcomer` / `to_sponsor` convert between the two.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .matching_service import Newcomer, Sponsor


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str


class NewcomerModel(BaseModel):
    member_id: str
    rank: int = Field(..., ge=1, description="pay-grade as an integer")
    mos: str
    family_status: str
    prior_station: bool = False
    interests: list[str] = Field(default_factory=list)
    efmp: bool = False
    gender: str | None = Field(default=None, description="audit only — never scored")

    def to_newcomer(self) -> Newcomer:
        return Newcomer(
            member_id=self.member_id,
            rank=self.rank,
            mos=self.mos,
            family_status=self.family_status,
            prior_station=self.prior_station,
            interests=set(self.interests),
            efmp=self.efmp,
            gender=self.gender,
        )


class SponsorModel(BaseModel):
    member_id: str
    rank: int = Field(..., ge=1)
    mos: str
    family_status: str
    prior_station: bool = False
    interests: list[str] = Field(default_factory=list)
    capacity: int = Field(1, ge=0)
    current_load: int = Field(0, ge=0)
    past_rating: float = Field(0.5, ge=0.0, le=1.0)
    efmp_knowledge: bool = False
    gender: str | None = None

    def to_sponsor(self) -> Sponsor:
        return Sponsor(
            member_id=self.member_id,
            rank=self.rank,
            mos=self.mos,
            family_status=self.family_status,
            prior_station=self.prior_station,
            interests=set(self.interests),
            capacity=self.capacity,
            current_load=self.current_load,
            past_rating=self.past_rating,
            efmp_knowledge=self.efmp_knowledge,
            gender=self.gender,
        )


class MatchRequest(BaseModel):
    """Match an explicit cohort. If both lists are empty, the server uses the
    synthetic cohort it loaded at startup."""

    newcomers: list[NewcomerModel] = Field(default_factory=list)
    sponsors: list[SponsorModel] = Field(default_factory=list)
    top_k: int = Field(3, ge=1, le=10)


class RecommendationModel(BaseModel):
    sponsor_id: str
    score: float
    reasons: list[str]


class MatchResultModel(BaseModel):
    newcomer_id: str
    recommendations: list[RecommendationModel]
    assigned_sponsor_id: str | None
    unmatched: bool


class ApproveRequest(BaseModel):
    sponsor_id: str = Field(..., description="the sponsor the coordinator confirms")
    override: bool = Field(False, description="true if this overrides the recommendation")


class ApprovedMatchModel(BaseModel):
    newcomer_id: str
    sponsor_id: str
    status: str  # "approved" | "override"
