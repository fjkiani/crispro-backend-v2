-- Migration: Add data_classification column to relevant tables
-- Purpose: Classify data as PHI vs NON_PHI for SAAS compliance and retention policies
-- Date: 2025-01-XX

-- Add data_classification column to patient_profiles
ALTER TABLE patient_profiles
ADD COLUMN IF NOT EXISTS data_classification TEXT DEFAULT 'PHI';

-- Add data_classification column to patient_care_plans
ALTER TABLE patient_care_plans
ADD COLUMN IF NOT EXISTS data_classification TEXT DEFAULT 'PHI';

-- Add data_classification column to patient_sessions
ALTER TABLE patient_sessions
ADD COLUMN IF NOT EXISTS data_classification TEXT DEFAULT 'PHI';

-- Add data_classification column to user_profiles (for general user data)
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS data_classification TEXT DEFAULT 'NON_PHI';

-- Add CHECK constraints for allowed values
ALTER TABLE patient_profiles
DROP CONSTRAINT IF EXISTS chk_data_classification_patient_profiles,
ADD CONSTRAINT chk_data_classification_patient_profiles
CHECK (data_classification IN ('PHI', 'NON_PHI', 'SENSITIVE', 'PUBLIC'));

ALTER TABLE patient_care_plans
DROP CONSTRAINT IF EXISTS chk_data_classification_patient_care_plans,
ADD CONSTRAINT chk_data_classification_patient_care_plans
CHECK (data_classification IN ('PHI', 'NON_PHI', 'SENSITIVE', 'PUBLIC'));

ALTER TABLE patient_sessions
DROP CONSTRAINT IF EXISTS chk_data_classification_patient_sessions,
ADD CONSTRAINT chk_data_classification_patient_sessions
CHECK (data_classification IN ('PHI', 'NON_PHI', 'SENSITIVE', 'PUBLIC'));

ALTER TABLE user_profiles
DROP CONSTRAINT IF EXISTS chk_data_classification_user_profiles,
ADD CONSTRAINT chk_data_classification_user_profiles
CHECK (data_classification IN ('PHI', 'NON_PHI', 'SENSITIVE', 'PUBLIC'));

-- Add indexes for faster filtering
CREATE INDEX IF NOT EXISTS idx_patient_profiles_data_classification ON patient_profiles(data_classification);
CREATE INDEX IF NOT EXISTS idx_patient_care_plans_data_classification ON patient_care_plans(data_classification);
CREATE INDEX IF NOT EXISTS idx_patient_sessions_data_classification ON patient_sessions(data_classification);

-- Add comments for documentation
COMMENT ON COLUMN patient_profiles.data_classification IS 'Data classification: PHI (Protected Health Information), NON_PHI, SENSITIVE, or PUBLIC';
COMMENT ON COLUMN patient_care_plans.data_classification IS 'Data classification: PHI (Protected Health Information), NON_PHI, SENSITIVE, or PUBLIC';
COMMENT ON COLUMN patient_sessions.data_classification IS 'Data classification: PHI (Protected Health Information), NON_PHI, SENSITIVE, or PUBLIC';
COMMENT ON COLUMN user_profiles.data_classification IS 'Data classification: PHI (Protected Health Information), NON_PHI, SENSITIVE, or PUBLIC';
