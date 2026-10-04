-- UNITE canonical schema (PostgreSQL) — v1.0
--
-- Lineage: this schema keeps the Alpha release's personnel / unit / PCS-queue
-- model and its original terminology (soldier_id, rank_tier, UIC, DA 5434),
-- then extends it with the v2 matching, interests, and audit tables needed by
-- the two-stage scorer + optimizer. Lines added in v2 are marked "v2:".
--
-- In dev, tests, and CI the app uses an in-memory store (backend/app/store.py)
-- so it runs without a database; this file is the canonical production target.
-- Everything is synthetic — no real PII is ever stored. (dod_id and full_name
-- from the original draft were intentionally dropped as forbidden PII.)

CREATE TYPE rank_tier_enum AS ENUM ('ENLISTED', 'NCO', 'WARRANT', 'OFFICER');
CREATE TYPE family_status_enum AS ENUM ('single', 'married', 'married_children');  -- v2
CREATE TYPE matching_state_enum AS ENUM (
    'UNASSIGNED', 'RECOMMENDED', 'COMPUTED_MATCH', 'MANUAL_OVERRIDE', 'ARCHIVED'
);

-- Units (original Alpha table, unchanged).
CREATE TABLE IF NOT EXISTS military_units (
    uic           VARCHAR(8) PRIMARY KEY,
    unit_name     VARCHAR(100) NOT NULL,
    base_location VARCHAR(100) NOT NULL
);

-- Personnel registry (original Alpha table). A single row can be an incoming
-- member and/or an available sponsor. v2 added the attributes the scorer reads.
CREATE TABLE IF NOT EXISTS personnel_registry (
    soldier_id           VARCHAR(10) PRIMARY KEY,
    rank_code            VARCHAR(5) NOT NULL,
    rank_tier            rank_tier_enum NOT NULL,
    mos_code             VARCHAR(4) NOT NULL,
    current_uic          VARCHAR(8) REFERENCES military_units(uic),
    is_available_sponsor BOOLEAN DEFAULT FALSE,
    active_load_count    INT DEFAULT 0 CHECK (active_load_count >= 0),
    max_load_capacity    INT DEFAULT 3,
    family_status        family_status_enum,   -- v2: feeds the family_match feature
    prior_station        BOOLEAN DEFAULT FALSE, -- v2: feeds prior_station_match
    past_rating          REAL DEFAULT 0.5 CHECK (past_rating BETWEEN 0 AND 1), -- v2: sponsor track record
    efmp                 BOOLEAN DEFAULT FALSE, -- v2: newcomer needs an EFMP-knowledgeable sponsor
    efmp_knowledge       BOOLEAN DEFAULT FALSE, -- v2: sponsor can support an EFMP newcomer
    gender               VARCHAR(8),            -- v2: audit only; NEVER used in scoring
    CHECK (active_load_count <= max_load_capacity)
);

-- Interests (v2): many-to-many, feed the shared_interests feature.
CREATE TABLE IF NOT EXISTS personnel_interests (
    soldier_id VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE CASCADE,
    interest   VARCHAR(40) NOT NULL,
    PRIMARY KEY (soldier_id, interest)
);

-- PCS inbound queue (original Alpha table, unchanged).
CREATE TABLE IF NOT EXISTS pcs_inbound_queue (
    pcs_tracking_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    soldier_id             VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE CASCADE,
    gaining_uic            VARCHAR(8) REFERENCES military_units(uic),
    projected_report_date  DATE NOT NULL,
    assigned_sponsor_id    VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE SET NULL,
    matching_status        matching_state_enum DEFAULT 'UNASSIGNED',
    da_5434_verified       BOOLEAN DEFAULT FALSE,
    last_updated_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Match recommendations + coordinator decisions (v2): records the compatibility
-- score and the plain-language reasons the matcher produced, for auditability.
CREATE TABLE IF NOT EXISTS match_recommendations (
    id                  SERIAL PRIMARY KEY,
    pcs_tracking_id     UUID REFERENCES pcs_inbound_queue(pcs_tracking_id) ON DELETE CASCADE,
    soldier_id          VARCHAR(10) NOT NULL REFERENCES personnel_registry(soldier_id) ON DELETE CASCADE,
    sponsor_id          VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE SET NULL,
    compatibility_score REAL CHECK (compatibility_score BETWEEN 0 AND 1),
    reasons             TEXT[],                                  -- plain-language explanation
    matching_status     matching_state_enum NOT NULL DEFAULT 'RECOMMENDED',
    decided_by          VARCHAR(32),                             -- coordinator/admin username
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Original Alpha index: only eligible sponsors with an open slot are scanned.
CREATE INDEX IF NOT EXISTS idx_sponsor_lookup_matrix
    ON personnel_registry (current_uic, is_available_sponsor, rank_tier)
    WHERE is_available_sponsor = TRUE AND active_load_count < max_load_capacity;

-- Original Alpha index: unassigned inbound members by gaining unit.
CREATE INDEX IF NOT EXISTS idx_inbound_unassigned_queue
    ON pcs_inbound_queue (gaining_uic, matching_status)
    WHERE matching_status = 'UNASSIGNED';

-- v2 index: look up recommendations/decisions per inbound member.
CREATE INDEX IF NOT EXISTS idx_match_recs_soldier
    ON match_recommendations (soldier_id, matching_status);
