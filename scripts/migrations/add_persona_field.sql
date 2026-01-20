-- Migration: Add persona field to user_profiles table
-- Date: January 2025
-- Purpose: Support persona-based access control (patient, oncologist, researcher)

-- Add persona column if it doesn't exist
ALTER TABLE public.user_profiles 
ADD COLUMN IF NOT EXISTS persona VARCHAR(50);

-- Add check constraint for valid persona values
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'user_profiles_persona_check'
    ) THEN
        ALTER TABLE public.user_profiles 
        ADD CONSTRAINT user_profiles_persona_check 
        CHECK (persona IN ('patient', 'oncologist', 'researcher'));
    END IF;
END $$;

-- Set default persona based on existing role
UPDATE public.user_profiles 
SET persona = CASE 
    WHEN role = 'clinician' THEN 'oncologist'
    WHEN role = 'oncologist' THEN 'oncologist'
    WHEN role = 'researcher' THEN 'researcher'
    WHEN role = 'admin' THEN 'researcher'
    WHEN role = 'enterprise' THEN 'researcher'
    ELSE 'patient'
END
WHERE persona IS NULL;

-- Set default for new records
ALTER TABLE public.user_profiles 
ALTER COLUMN persona SET DEFAULT 'researcher';

-- Create index for persona lookups
CREATE INDEX IF NOT EXISTS idx_user_profiles_persona 
ON public.user_profiles(persona);

-- Add comment
COMMENT ON COLUMN public.user_profiles.persona IS 
'User persona for access control: patient, oncologist, or researcher';

