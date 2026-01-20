-- Migration: Add MFA (Multi-Factor Authentication) columns to user_profiles
-- Purpose: Enable MFA for admin users and PHI access (HIPAA requirement)
-- Date: 2025-01-XX

-- Add MFA columns to user_profiles table
ALTER TABLE user_profiles
ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS mfa_secret TEXT,
ADD COLUMN IF NOT EXISTS mfa_verified_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS mfa_backup_codes TEXT[]; -- Array of backup codes

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_mfa_enabled ON user_profiles(mfa_enabled) WHERE mfa_enabled = TRUE;

-- Add comment for documentation
COMMENT ON COLUMN user_profiles.mfa_enabled IS 'Whether MFA is enabled for this user';
COMMENT ON COLUMN user_profiles.mfa_secret IS 'TOTP secret key (encrypted at application level)';
COMMENT ON COLUMN user_profiles.mfa_verified_at IS 'Timestamp of last successful MFA verification';
COMMENT ON COLUMN user_profiles.mfa_backup_codes IS 'Array of backup codes for MFA recovery';
