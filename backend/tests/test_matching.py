import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_perfect_mos_and_rank_match():
    """Confirms precise vector evaluation match if MOS and Rank traits align perfectly."""
    payload = {
        "soldier_id": "S-CORE",
        "rank_tier": "NCO",
        "mos_code": "11B",
        "gaining_uic": "WAAAAA"
    }
    response = client.post("/api/v1/pcs/compute-match", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["assigned_sponsor_id"] == "SP-9901"
    assert data["status"] == "COMPUTED_MATCH"
    assert data["compatibility_score"] >= 0.85

def test_fallback_routing_on_mismatch_tier():
    """Verifies assignment isolation fallback if rank boundaries present severe distance variances."""
    payload = {
        "soldier_id": "S-OFFICER",
        "rank_tier": "OFFICER",
        "mos_code": "92Y",
        "gaining_uic": "WAAAAA"
    }
    response = client.post("/api/v1/pcs/compute-match", json=payload)
    assert response.status_code == 200
    data = response.json()
    # Should fall back due to lack of an officer with matching skills or fallback tolerance limits
    assert data["assigned_sponsor_id"] == "SP-9903" # Matches Rank Tier, missing MOS