"""Legacy v1 endpoint tests — ported from the Alpha release.

Retained to prove the original Alpha heuristic still works alongside the v2
matcher. The two tests are the Alpha's originals, adapted to the package layout.
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_legacy_perfect_mos_and_rank_match():
    """Perfect MOS + rank tier alignment yields the top sponsor and a high score."""
    payload = {
        "soldier_id": "S-CORE",
        "rank_tier": "NCO",
        "mos_code": "11B",
        "gaining_uic": "WAAAAA",
    }
    resp = client.post("/api/v1/pcs/compute-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_sponsor_id"] == "SP-9901"
    assert data["status"] == "COMPUTED_MATCH"
    assert data["compatibility_score"] >= 0.85


def test_legacy_fallback_on_mismatch_tier():
    """An officer with no MOS match falls back to the rank-tier-aligned sponsor."""
    payload = {
        "soldier_id": "S-OFF",
        "rank_tier": "OFFICER",
        "mos_code": "92Y",
        "gaining_uic": "WAAAAA",
    }
    resp = client.post("/api/v1/pcs/compute-match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_sponsor_id"] == "SP-9903"  # matches rank tier, missing MOS
