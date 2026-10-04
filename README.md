# UNITE — Unit Newcomer Integration & Transition Engine

**Release v1.0.** The integrated final release of the TASP Placement & Matching
platform. It recommends compatible **sponsors** for incoming service members during a
Permanent Change of Station (PCS), so onboarding is faster and better-matched than the
current manual process. This release evolves directly from the deployed **Alpha**
(see *Lineage* below), not a from-scratch rewrite.

> Educational prototype. Runs entirely on **synthetic data** — no real PII, and no
> connection to any live DoD system.

---

## Lineage — from Alpha to v1.0

This release is a deliberate evolution of the Alpha, preserving continuity rather than
replacing it:

- **The Alpha's matching endpoint is retained, deprecated.** The original single-sponsor
  greedy heuristic still lives at `POST /api/v1/pcs/compute-match` (see
  `backend/app/legacy.py`), marked deprecated so it renders struck-through in the OpenAPI
  docs. It keeps the Alpha's original terminology (`soldier_id`, `rank_tier`,
  `gaining_uic`) and its mock sponsor pool, so a reader can see the old feature sitting
  next to the v2 optimizer that supersedes it. Its two original tests still pass
  (`backend/tests/test_legacy.py`).
- **The schema is the Alpha's, extended.** `db/schema.sql` keeps the Alpha's
  `military_units` / `personnel_registry` / `pcs_inbound_queue` model, original
  terminology, and DA-5434 field, then adds the v2 tables the matcher needs
  (interests, `match_recommendations` with score + reasons). v2 additions are marked
  `-- v2:` in the file.
- **The AI feature grew from greedy to optimal.** Alpha picked one best sponsor per
  request; v2 scores every pair and assigns the whole cohort optimally under capacity
  and eligibility constraints (`POST /v1/match`).

### Terminology map (Alpha ↔ v1.0 code)

The canonical schema uses the Alpha's vocabulary; the v2 application code uses the names
below. They refer to the same concepts.

| Alpha / schema term | v2 code term |
|---|---|
| `soldier_id` | `member_id` |
| `rank_tier` (enum) | `rank` (integer pay-grade) |
| `gaining_uic` / `current_uic` | unit scoping (not modeled in the in-memory demo) |
| inbound soldier | `newcomer` |
| `compatibility_score` | `score` |

---

## What's in this Alpha

An end-to-end vertical slice: a synthetic cohort goes in, ranked-and-explained sponsor
recommendations come out, and a coordinator reviews and approves them.

- **Matching service (the AI feature)** — a transparent content-based scorer plus a
  capacity- and eligibility-constrained optimizer. Returns a ranked top-3 per newcomer,
  each with a plain-language reason.
- **FastAPI backend** — auth, profiles, matching, and approvals over HTTP/JSON.
- **React dashboard** — one screen to run a cohort, review recommendations, and
  approve or override.
- **CI** — GitHub Actions runs `ruff` lint and the `pytest` suite on every push and PR.

The matching service is the intelligence; a human always makes the final call. The
service recommends, the coordinator decides.

---

## Architecture

```
Coordinator ─► React Dashboard ──HTTP/JSON──► FastAPI Backend
                                                │
                                                ├─► Matching Service  (scorer + optimizer)
                                                └─► Data Store        (in-memory in dev; PostgreSQL in prod)
```

In dev, tests, and CI the backend uses an in-memory store seeded with synthetic
profiles, so nothing external is required to run it. `db/schema.sql` is the canonical
PostgreSQL schema for production; swapping stores means replacing
`backend/app/store.py`, not the API.

---

## The AI feature — two-stage matching

**Stage 1 — Compatibility scoring.** For every (newcomer, sponsor) pair, a weighted sum
over comparable features yields a score in `[0, 1]`. No training data required.

Features and weights (they sum to 1.0):

| Feature | Weight | Meaning |
|---|---|---|
| `same_mos` | 0.30 | identical job specialty |
| `rank_proximity` | 0.20 | closeness in pay-grade |
| `family_match` | 0.15 | similar family situation |
| `shared_interests` | 0.15 | Jaccard overlap of interests |
| `sponsor_track_record` | 0.10 | historical survey rating |
| `prior_station_match` | 0.10 | sponsor familiar with the installation |

**Protected attributes (gender, race, sexual orientation, ethnicity) are never read by
the scorer.** `gender` exists on the profiles for auditing only and is not a parameter
of any scoring function. `test_scorer.py::test_gender_is_never_scored` enforces this.

**Stage 2 — Constrained assignment.** Sponsors are assigned across the whole cohort to
maximize total compatibility, subject to hard constraints (remaining capacity, and EFMP
eligibility: an EFMP newcomer may only pair with an EFMP-knowledgeable sponsor). Solved
as an assignment problem with `scipy.optimize.linear_sum_assignment`. When demand
exceeds capacity, affected newcomers come back as a structured `unmatched` result
rather than failing silently.

---

## Getting started

### 1. Matching service, standalone

The matcher runs on synthetic data with just NumPy + SciPy:

```bash
cd backend
python -m pip install numpy scipy
python -m app.matching_service
```

Expected output:

```
Recommended matches (for coordinator approval):
  N1 -> S11  score=0.58  because: same job specialty (MOS), close in rank, familiar with this installation
  ...
```

### 2. Backend API

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload      # http://localhost:8000  (docs at /docs)
```

Quick check:

```bash
curl localhost:8000/health
curl -X POST localhost:8000/v1/match -H "Content-Type: application/json" -d '{}'
```

### 3. Dashboard

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173 (proxies to the backend)
```

Sign in with the demo coordinator account (`coordinator` / `unite-demo`) to approve or
override. Run matching, expand any newcomer to see the ranked top-3 with reasons.

### 4. Tests and lint (what CI runs)

```bash
pip install -r backend/requirements.txt
ruff check .
pytest -v --cov=app --cov-report=term-missing
```

The suite includes the ported Alpha tests (`test_legacy.py`) alongside the v2 scorer,
optimizer, API, hit-rate, and fairness tests. CI reports line coverage (currently ~95%).

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/v1/auth/login` | Mock role-based login (coordinator / admin) |
| GET | `/v1/newcomers` | List incoming members needing a sponsor |
| POST | `/v1/match` | Generate ranked top-3 recommendations for a cohort |
| POST | `/v1/matches/{newcomer_id}/approve` | Approve or override a recommendation (auth required) |
| GET | `/v1/matches` | Recorded coordinator decisions |
| POST | `/api/v1/pcs/compute-match` | **Deprecated (v1)** — Alpha single-sponsor heuristic, kept for lineage |

`POST /v1/match` with an empty body `{}` matches the synthetic cohort loaded at startup.
Supply `newcomers` and `sponsors` arrays to match an explicit cohort. Response per
newcomer:

```json
{
  "newcomer_id": "N1",
  "recommendations": [
    { "sponsor_id": "S46", "score": 0.62, "reasons": ["same job specialty (MOS)", "close in rank"] }
  ],
  "assigned_sponsor_id": "S46",
  "unmatched": false
}
```

---

## Requirements this Alpha meets

**Functional:** mock role-based auth; store and list synthetic profiles; generate
profiles on demand; compute a compatibility score for every pair; return a ranked top-3
per newcomer with reasons; enforce capacity and EFMP constraints; approve/override;
show current and recorded matches.

**Non-functional:**
- *Performance* — top-3 for 100 newcomers vs. 600 sponsors in well under 3s
  (`test_optimizer.py::test_performance_100_by_600_under_3s`).
- *Match quality* — top-3 hit rate ≥ 70% on a held-out synthetic set
  (`test_hit_rate.py`). This is a ranking metric, not classification accuracy.
- *Fairness* — protected attributes excluded from scoring (enforced by test).
- *Reliability* — demand over capacity returns a structured `unmatched` result.
- *Usability* — a coordinator reviews an entire cohort from one screen.

---

## Repository layout

```
unite/
├── README.md
├── pyproject.toml              # pytest + ruff config
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI app + routes
│   │   ├── matching_service.py # scorer + constrained optimizer (the AI feature)
│   │   ├── synthetic_data.py   # synthetic profile generator
│   │   ├── models.py           # Pydantic wire models
│   │   ├── auth.py             # mock role-based login (salted-hashed passwords)
│   │   ├── store.py            # in-memory data store (PostgreSQL stand-in)
│   │   └── legacy.py           # deprecated Alpha v1 endpoint, kept for lineage
│   └── tests/                  # scorer, optimizer, API, hit-rate, fairness, legacy-v1
├── db/
│   └── schema.sql              # canonical PostgreSQL schema
├── frontend/                   # React (Vite) coordinator dashboard
└── .github/workflows/ci.yml    # GitHub Actions: ruff + pytest
```

---

## AI-assisted development policy

AI assistance is used for synthetic data, unit tests, edge cases, and boilerplate
(FastAPI stubs, React components). Any AI-generated code must be read and understood by
a developer, goes through the same PR + peer review as any other contribution, must
pass CI before review, and AI-generated tests get extra scrutiny. Changes to
fairness/eligibility logic require a second reviewer.

---

## Scope boundaries (documented, not built)

Live integration with DoD systems (TASP, DEERS); production security authorization
(IL4/IL5, ATO, CAC/PIV); a learned/ML scorer (deferred until labeled synthetic outcomes
exist — the content-based scorer is the first stage behind the same interface); and
predictive PCS-demand analytics (a different problem from matching).

## Team (Team 1)

Lead Architect — Salim Al-Kizim · Interface Designers — Amadou Djigo, Jacquis Wright ·
Integration Lead — Ryan Hinely
