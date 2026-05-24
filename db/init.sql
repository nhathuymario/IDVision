-- ============================================================
-- IDVision Database Schema
-- PostgreSQL + pgvector for Face Recognition Attendance System
-- ============================================================

-- Enable pgvector extension for face embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table: employees
-- Stores employee information and face embeddings (512-dim ArcFace)
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    employee_code VARCHAR(50) UNIQUE NOT NULL,
    department VARCHAR(100),
    telegram_chat_id VARCHAR(50),           -- For personal Telegram notifications
    password_hash VARCHAR(255),             -- Bcrypt hash for password-based check-in
    face_encoding VECTOR(512),              -- ArcFace 512-dimensional embedding
    enrolled_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Table: attendance_logs
-- Records every check-in event with confidence scoring
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance_logs (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    check_in_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    check_method VARCHAR(20) DEFAULT 'FACE' CHECK (check_method IN ('FACE', 'PASSWORD')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('SUCCESS', 'LATE', 'LOW_CONFIDENCE')),
    confidence FLOAT,                       -- Cosine similarity score (0.0 - 1.0)
    snapshot_path VARCHAR(500),             -- Path to face snapshot at check-in time
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Table: admin_users
-- Admin accounts for dashboard access
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Table: attendance_policies
-- Global attendance schedule and payroll configuration
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance_policies (
    id SERIAL PRIMARY KEY,
    timezone VARCHAR(100) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    work_start_time TIME NOT NULL,
    break_start_time TIME NOT NULL,
    break_end_time TIME NOT NULL,
    work_end_time TIME NOT NULL,
    late_grace_minutes INTEGER NOT NULL DEFAULT 0,
    hourly_wage FLOAT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default admin account (password: admin123 — CHANGE IN PRODUCTION)
-- bcrypt hash of 'admin123'
INSERT INTO admin_users (username, password_hash, full_name)
VALUES ('admin', '$2b$12$xtZgEHSgA9TE5NuUV1SCj..LijmvQ0ZXb9AjWlYEuUytpTqj8XT/m', 'Administrator')
ON CONFLICT (username) DO NOTHING;

-- Default attendance policy
INSERT INTO attendance_policies (
    timezone,
    work_start_time,
    break_start_time,
    break_end_time,
    work_end_time,
    late_grace_minutes,
    hourly_wage
)
VALUES ('Asia/Ho_Chi_Minh', '08:00', '12:00', '13:00', '17:30', 0, 0)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Indexes for Performance
-- ============================================================

-- HNSW index for fast approximate nearest neighbor search on face embeddings
CREATE INDEX IF NOT EXISTS idx_employees_face_encoding 
    ON employees USING hnsw (face_encoding vector_cosine_ops);

-- Index for querying attendance by date range
CREATE INDEX IF NOT EXISTS idx_attendance_checkin_time 
    ON attendance_logs (check_in_time);

-- Index for querying attendance by employee
CREATE INDEX IF NOT EXISTS idx_attendance_employee_id 
    ON attendance_logs (employee_id);

-- Composite index for duplicate check (employee + recent time)
CREATE INDEX IF NOT EXISTS idx_attendance_employee_time 
    ON attendance_logs (employee_id, check_in_time DESC);

-- Index for active employees lookup
CREATE INDEX IF NOT EXISTS idx_employees_active 
    ON employees (is_active) WHERE is_active = TRUE;
