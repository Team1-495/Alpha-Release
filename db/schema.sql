-- Fixed from the original DatabaseSQL:
--   1. added the missing rank_tier_enum definition (the file used it but never created it)
--   2. removed dod_id and full_name (PII the project forbids)
-- Everything else is the teammate's original design, unchanged.

CREATE TYPE rank_tier_enum AS ENUM ('ENLISTED', 'NCO', 'WARRANT', 'OFFICER');
CREATE TYPE matching_state_enum AS ENUM ('UNASSIGNED', 'COMPUTED_MATCH', 'MANUAL_OVERRIDE', 'ARCHIVED');

CREATE TABLE IF NOT EXISTS military_units (
    uic VARCHAR(8) PRIMARY KEY,
    unit_name VARCHAR(100) NOT NULL,
    base_location VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS personnel_registry (
    soldier_id VARCHAR(10) PRIMARY KEY,
    rank_code VARCHAR(5) NOT NULL,
    rank_tier rank_tier_enum NOT NULL,
    mos_code VARCHAR(4) NOT NULL,
    current_uic VARCHAR(8) REFERENCES military_units(uic),
    is_available_sponsor BOOLEAN DEFAULT FALSE,
    active_load_count INT DEFAULT 0 CHECK (active_load_count >= 0),
    max_load_capacity INT DEFAULT 3
);

CREATE TABLE IF NOT EXISTS pcs_inbound_queue (
    pcs_tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    soldier_id VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE CASCADE,
    gaining_uic VARCHAR(8) REFERENCES military_units(uic),
    projected_report_date DATE NOT NULL,
    assigned_sponsor_id VARCHAR(10) REFERENCES personnel_registry(soldier_id) ON DELETE SET NULL,
    matching_status matching_state_enum DEFAULT 'UNASSIGNED',
    da_5434_verified BOOLEAN DEFAULT FALSE,
    last_updated_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sponsor_lookup_matrix
ON personnel_registry (current_uic, is_available_sponsor, rank_tier)
WHERE is_available_sponsor = TRUE AND active_load_count < max_load_capacity;

CREATE INDEX idx_inbound_unassigned_queue
ON pcs_inbound_queue (gaining_uic, matching_status)
WHERE matching_status = 'UNASSIGNED';
