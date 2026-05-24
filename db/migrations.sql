-- Migration script to add new columns to attendance_logs table
-- This supports the multi-check-in per day feature

-- Add new columns to track check-out time and period type
ALTER TABLE attendance_logs
ADD COLUMN IF NOT EXISTS check_out_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS period_type VARCHAR(20) DEFAULT 'MORNING_START' NOT NULL;

-- Drop old constraint if exists and add new one
ALTER TABLE attendance_logs
DROP CONSTRAINT IF EXISTS valid_status;

ALTER TABLE attendance_logs
ADD CONSTRAINT valid_status CHECK (status IN ('SUCCESS', 'LATE', 'LOW_CONFIDENCE'));

-- Add period type constraint
ALTER TABLE attendance_logs
DROP CONSTRAINT IF EXISTS valid_period_type;

ALTER TABLE attendance_logs
ADD CONSTRAINT valid_period_type CHECK (period_type IN ('MORNING_START', 'LUNCH_START', 'LUNCH_END', 'EVENING_END'));

-- Create index for faster queries by period type
CREATE INDEX IF NOT EXISTS idx_attendance_period
ON attendance_logs (employee_id, check_in_time, period_type);

