-- =============================================
-- schema.sql - Database Schema for Home Rehab Coach
-- Run this ONCE to create all tables
-- =============================================

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS workouts;
DROP TABLE IF EXISTS caregiver_patient;
DROP TABLE IF EXISTS doctor_patient;
DROP TABLE IF EXISTS exercises;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS users;

-- =============================================
-- 1. USERS TABLE
-- Stores all users: doctors, patients, caregivers
-- =============================================
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('doctor', 'patient', 'caregiver')),
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 2. PATIENTS TABLE
-- Additional info for users with role='patient'
-- =============================================
CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    condition TEXT NOT NULL,
    surgery_date DATE,
    current_week INTEGER DEFAULT 1,
    adherence_rate REAL DEFAULT 0,
    avg_pain_level REAL DEFAULT 0,
    avg_quality_score REAL DEFAULT 0,
    streak_days INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================
-- 3. DOCTOR_PATIENT TABLE
-- Maps doctors to their patients
-- =============================================
CREATE TABLE doctor_patient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    assigned_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(doctor_id, patient_id)
);

-- =============================================
-- 4. CAREGIVER_PATIENT TABLE
-- Maps caregivers to patients they monitor
-- =============================================
CREATE TABLE caregiver_patient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caregiver_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    relationship TEXT,
    FOREIGN KEY (caregiver_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(caregiver_id, patient_id)
);

-- =============================================
-- 5. EXERCISES TABLE
-- Library of all available exercises
-- =============================================
CREATE TABLE exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    video_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 6. WORKOUTS TABLE
-- Exercise assignments for patients
-- =============================================
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    sets INTEGER DEFAULT 3,
    reps INTEGER DEFAULT 10,
    hold_time INTEGER DEFAULT 5,
    rest_time INTEGER DEFAULT 30,
    frequency TEXT DEFAULT 'Daily',
    rom_target INTEGER,
    instructions TEXT,
    is_active INTEGER DEFAULT 1,
    assigned_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
);

-- =============================================
-- 7. SESSIONS TABLE
-- Completed rehab sessions
-- =============================================
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    workout_id INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pain_before INTEGER,
    pain_after INTEGER,
    effort_level INTEGER,
    quality_score INTEGER,
    sets_completed INTEGER,
    reps_completed INTEGER,
    notes TEXT,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);

-- =============================================
-- 8. APPOINTMENTS TABLE
-- Scheduled consultations with video call support
-- =============================================
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TEXT NOT NULL,
    duration INTEGER DEFAULT 30,
    status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'completed', 'cancelled')),
    notes TEXT,
    room_id TEXT,  -- Unique room ID for video calls
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================
-- INSERT SAMPLE EXERCISES
-- =============================================
INSERT INTO exercises (name, description, category) VALUES
('Knee Extension', 'Seated leg raises to strengthen quadriceps', 'Knee'),
('Hip Flexor Stretch', 'Stretching hip flexors for improved mobility', 'Hip'),
('Quad Strengthening', 'Resistance-based quadriceps exercises', 'Knee'),
('Hamstring Curl', 'Lying hamstring curls for balance', 'Knee'),
('Calf Raises', 'Standing calf raises for lower leg strength', 'Knee'),
('Wall Slides', 'Back against wall squatting motion', 'Knee'),
('Shoulder Rotation', 'Gentle shoulder rotation exercises', 'Shoulder'),
('Back Extension', 'Lying back extension for spine mobility', 'Back'),
('Ankle Circles', 'Circular ankle movements for mobility', 'Ankle'),
('Glute Bridge', 'Hip thrust exercise for glute activation', 'Hip');

-- =============================================
-- INSERT SAMPLE DATA FOR TESTING
-- =============================================

-- Sample Doctor (password: doctor123)
INSERT INTO users (email, password, name, role) VALUES
('dr.smith@clinic.com', 'pbkdf2:sha256:600000$X7KxQF3Z$8e5c7b2f8d9a4e3b6c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b', 'Dr. Sarah Smith', 'doctor');

-- Sample Patients (password: patient123)
INSERT INTO users (email, password, name, role) VALUES
('john@email.com', 'pbkdf2:sha256:600000$Y8LyRG4A$9f6d8c3e9a5b4c2d7e8f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d', 'John Smith', 'patient'),
('maria@email.com', 'pbkdf2:sha256:600000$Y8LyRG4A$9f6d8c3e9a5b4c2d7e8f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d', 'Maria Garcia', 'patient'),
('robert@email.com', 'pbkdf2:sha256:600000$Y8LyRG4A$9f6d8c3e9a5b4c2d7e8f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d', 'Robert Johnson', 'patient'),
('emily@email.com', 'pbkdf2:sha256:600000$Y8LyRG4A$9f6d8c3e9a5b4c2d7e8f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d', 'Emily Chen', 'patient');

-- Sample Caregiver (password: care123)
INSERT INTO users (email, password, name, role) VALUES
('caregiver@email.com', 'pbkdf2:sha256:600000$Z9MzSH5B$af7e9d4f0b6c5d3e8f9a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e', 'Jane Doe', 'caregiver');

-- Patient medical info
INSERT INTO patients (user_id, condition, surgery_date, current_week, adherence_rate, avg_pain_level, avg_quality_score, streak_days) VALUES
(2, 'Knee Replacement', '2026-01-15', 3, 45, 4.2, 68, 2),
(3, 'Hip Surgery', '2026-01-01', 5, 82, 7, 75, 8),
(4, 'ACL Reconstruction', '2026-01-22', 2, 30, 3.5, 72, 0),
(5, 'Shoulder Rehab', '2025-12-20', 4, 92, 2, 85, 12);

-- Assign patients to doctor (Dr. Smith has all patients)
INSERT INTO doctor_patient (doctor_id, patient_id) VALUES
(1, 2), (1, 3), (1, 4), (1, 5);

-- Assign caregiver to patient (Jane monitors John)
INSERT INTO caregiver_patient (caregiver_id, patient_id, relationship) VALUES
(6, 2, 'Family Member');

-- Sample workouts for John Smith (user_id = 2)
INSERT INTO workouts (patient_id, exercise_id, sets, reps, frequency, instructions) VALUES
(2, 1, 3, 10, '3x per week', 'Keep back straight. Stop if pain exceeds 4/10.'),
(2, 2, 2, 1, 'Daily', 'Hold for 30 seconds each side.');

-- Sample appointments with room_ids for video calls
INSERT INTO appointments (doctor_id, patient_id, appointment_date, appointment_time, duration, notes, room_id) VALUES
(1, 2, '2026-02-10', '10:00', 30, 'Weekly check-in', 'rehab-1-2-abc12345'),
(1, 3, '2026-02-11', '14:00', 30, 'Pain assessment', 'rehab-1-3-def67890'),
(1, 5, '2026-02-12', '11:00', 15, 'Quick follow-up', 'rehab-1-5-ghi11223'),
(1, 4, '2026-02-13', '09:30', 45, 'ACL progress review', 'rehab-1-4-jkl44556');
