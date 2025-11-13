-- Migration: Add Microsoft Teams support to lead_assignments table
-- This allows assigning leads to Teams users (Azure AD) in addition to database users

-- Step 1: Make assigned_to_user_id nullable (for Teams-only assignments)
ALTER TABLE lead_assignments
ALTER COLUMN assigned_to_user_id DROP NOT NULL;

-- Step 2: Add Teams user columns
ALTER TABLE lead_assignments
ADD COLUMN IF NOT EXISTS assigned_to_teams_id TEXT,
ADD COLUMN IF NOT EXISTS assigned_to_name TEXT,
ADD COLUMN IF NOT EXISTS assigned_to_email TEXT;

-- Step 3: Add constraint to ensure at least one assignment target exists
ALTER TABLE lead_assignments
ADD CONSTRAINT check_assignment_target
CHECK (
    assigned_to_user_id IS NOT NULL
    OR assigned_to_teams_id IS NOT NULL
);

-- Step 4: Create index for Teams user lookups
CREATE INDEX IF NOT EXISTS idx_lead_assignments_teams_id
ON lead_assignments(assigned_to_teams_id);

-- Step 5: Update RLS policies to include Teams users
-- Drop existing policies
DROP POLICY IF EXISTS "Users view relevant assignments" ON lead_assignments;
DROP POLICY IF EXISTS "Recipients update assignment status" ON lead_assignments;

-- Create new policies that support both database and Teams users
CREATE POLICY "Users view relevant assignments"
ON lead_assignments FOR SELECT
USING (
    assigned_from_user_id = current_user_id()
    OR assigned_to_user_id = current_user_id()
    -- Note: Teams users won't have current_user_id(), they'll view via API
);

CREATE POLICY "Recipients update assignment status"
ON lead_assignments FOR UPDATE
USING (assigned_to_user_id = current_user_id());

-- Note: Teams users will use service role for updates, not RLS
