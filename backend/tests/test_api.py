"""API integration tests using FastAPI's TestClient."""

import pytest
from app.main import app
from app.store import store
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_store():
    store.seed_synthetic(n_newcomers=10, n_sponsors=30, seed=5)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _token(client) -> str:
    resp = client.post(
        "/v1/auth/login", json={"username": "coordinator", "password": "unite-demo"}
    )
    assert resp.status_code == 200
    return resp.json()["token"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_success_and_failure(client):
    ok = client.post(
        "/v1/auth/login", json={"username": "admin", "password": "unite-admin"}
    )
    assert ok.status_code == 200
    assert ok.json()["role"] == "admin"

    bad = client.post(
        "/v1/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert bad.status_code == 401


def test_list_newcomers(client):
    resp = client.get("/v1/newcomers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 10
    assert "gender" in body[0]  # present for audit, but never used in scoring


def test_match_returns_ranked_top3_with_reasons(client):
    resp = client.post("/v1/match", json={"newcomers": [], "sponsors": [], "top_k": 3})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 10
    first = results[0]
    assert "recommendations" in first
    assert len(first["recommendations"]) <= 3
    if first["recommendations"]:
        rec = first["recommendations"][0]
        assert 0.0 <= rec["score"] <= 1.0
        assert isinstance(rec["reasons"], list) and rec["reasons"]


def test_match_with_explicit_cohort(client):
    payload = {
        "newcomers": [
            {"member_id": "N1", "rank": 5, "mos": "11B", "family_status": "single"}
        ],
        "sponsors": [
            {
                "member_id": "S1",
                "rank": 5,
                "mos": "11B",
                "family_status": "single",
                "capacity": 1,
                "past_rating": 0.9,
            }
        ],
        "top_k": 3,
    }
    resp = client.post("/v1/match", json=payload)
    assert resp.status_code == 200
    result = resp.json()[0]
    assert result["assigned_sponsor_id"] == "S1"
    assert result["unmatched"] is False


def test_approve_requires_auth(client):
    client.post("/v1/match", json={})
    resp = client.post("/v1/matches/N1/approve", json={"sponsor_id": "S1"})
    assert resp.status_code == 401


def test_approve_and_override_flow(client):
    match = client.post("/v1/match", json={}).json()
    target = match[0]
    newcomer_id = target["newcomer_id"]
    recommended = target["recommendations"][0]["sponsor_id"]

    headers = {"Authorization": f"Bearer {_token(client)}"}

    # Approve the recommended sponsor.
    approve = client.post(
        f"/v1/matches/{newcomer_id}/approve",
        json={"sponsor_id": recommended},
        headers=headers,
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    # Override with a sponsor that was not recommended.
    override = client.post(
        f"/v1/matches/{newcomer_id}/approve",
        json={"sponsor_id": "S-NOT-RECOMMENDED", "override": True},
        headers=headers,
    )
    assert override.status_code == 200
    assert override.json()["status"] == "override"

    listing = client.get("/v1/matches").json()
    assert any(m["newcomer_id"] == newcomer_id for m in listing)
