-- Patient Dossiers Metadata Table
-- Stores metadata about generated dossiers for search and management
-- Actual markdown/JSON files stored in file system: .cursor/patients/{patient_id}/dossiers/

CREATE TABLE IF NOT EXISTS patient_dossiers (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    nct_id VARCHAR(50) NOT NULL,
    dossier_id VARCHAR(255) UNIQUE NOT NULL,
    tier VARCHAR(20),  -- 'TOP_TIER', 'GOOD_TIER', 'OK_TIER'
    match_score FLOAT,
    file_path TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(patient_id, nct_id)
);

CREATE INDEX idx_patient_dossiers_patient_id ON patient_dossiers(patient_id);
CREATE INDEX idx_patient_dossiers_nct_id ON patient_dossiers(nct_id);
CREATE INDEX idx_patient_dossiers_tier ON patient_dossiers(tier);
CREATE INDEX idx_patient_dossiers_match_score ON patient_dossiers(match_score DESC);


