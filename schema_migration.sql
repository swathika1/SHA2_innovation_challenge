-- Schema Migration for Optimization Integration
-- This adds tables and fields needed for real-time appointment optimization

-- Timeslots table (define available appointment slots)
CREATE TABLE IF NOT EXISTS timeslots (
    id TEXT PRIMARY KEY,
    day TEXT NOT NULL,
    time TEXT NOT NULL,
    time_index INTEGER NOT NULL,
    label TEXT NOT NULL
);

-- Doctor specialties (many-to-many)
CREATE TABLE IF NOT EXISTS doctor_specialties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    specialty TEXT NOT NULL,
    FOREIGN KEY (doctor_id) REFERENCES users(id),
    UNIQUE(doctor_id, specialty)
);

-- Doctor availability (which timeslots each doctor is available)
CREATE TABLE IF NOT EXISTS doctor_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    timeslot_id TEXT NOT NULL,
    available INTEGER DEFAULT 1,
    FOREIGN KEY (doctor_id) REFERENCES users(id),
    FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
    UNIQUE(doctor_id, timeslot_id)
);

-- Doctor location (for distance calculations)
CREATE TABLE IF NOT EXISTS doctor_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL UNIQUE,
    clinic_name TEXT,
    address TEXT,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (doctor_id) REFERENCES users(id)
);

-- Patient availability (which timeslots patient is available)
CREATE TABLE IF NOT EXISTS patient_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    timeslot_id TEXT NOT NULL,
    available INTEGER DEFAULT 1,
    FOREIGN KEY (patient_id) REFERENCES users(id),
    FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
    UNIQUE(patient_id, timeslot_id)
);

-- Patient time preferences (preference score 0-1 for each timeslot)
CREATE TABLE IF NOT EXISTS patient_time_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    timeslot_id TEXT NOT NULL,
    preference_score REAL DEFAULT 0.5,
    FOREIGN KEY (patient_id) REFERENCES users(id),
    FOREIGN KEY (timeslot_id) REFERENCES timeslots(id),
    UNIQUE(patient_id, timeslot_id)
);

-- Alter existing patients table to add optimization fields
-- Note: SQLite doesn't support ALTER COLUMN, so we add new columns
-- If column already exists, SQLite will ignore it

-- Add urgency level (Low, Medium, High)
ALTER TABLE patients ADD COLUMN urgency TEXT DEFAULT 'Medium' CHECK(urgency IN ('Low', 'Medium', 'High'));

-- Add max distance willing to travel (in km)
ALTER TABLE patients ADD COLUMN max_distance REAL DEFAULT 20.0;

-- Add specialty needed
ALTER TABLE patients ADD COLUMN specialty_needed TEXT;

-- Add preferred/continuity doctor
ALTER TABLE patients ADD COLUMN preferred_doctor_id INTEGER REFERENCES users(id);

-- Add patient location (for distance calculations)
ALTER TABLE patients ADD COLUMN address TEXT;
ALTER TABLE patients ADD COLUMN latitude REAL;
ALTER TABLE patients ADD COLUMN longitude REAL;

-- Insert default timeslots (Monday-Friday, 9am-5pm)
INSERT OR IGNORE INTO timeslots (id, day, time, time_index, label) VALUES
('mon_9am', 'Monday', '9:00 AM', 0, 'Mon 9:00 AM'),
('mon_10am', 'Monday', '10:00 AM', 1, 'Mon 10:00 AM'),
('mon_11am', 'Monday', '11:00 AM', 2, 'Mon 11:00 AM'),
('mon_1pm', 'Monday', '1:00 PM', 3, 'Mon 1:00 PM'),
('mon_2pm', 'Monday', '2:00 PM', 4, 'Mon 2:00 PM'),
('mon_3pm', 'Monday', '3:00 PM', 5, 'Mon 3:00 PM'),
('mon_4pm', 'Monday', '4:00 PM', 6, 'Mon 4:00 PM'),
('tue_9am', 'Tuesday', '9:00 AM', 7, 'Tue 9:00 AM'),
('tue_10am', 'Tuesday', '10:00 AM', 8, 'Tue 10:00 AM'),
('tue_11am', 'Tuesday', '11:00 AM', 9, 'Tue 11:00 AM'),
('tue_1pm', 'Tuesday', '1:00 PM', 10, 'Tue 1:00 PM'),
('tue_2pm', 'Tuesday', '2:00 PM', 11, 'Tue 2:00 PM'),
('tue_3pm', 'Tuesday', '3:00 PM', 12, 'Tue 3:00 PM'),
('tue_4pm', 'Tuesday', '4:00 PM', 13, 'Tue 4:00 PM'),
('wed_9am', 'Wednesday', '9:00 AM', 14, 'Wed 9:00 AM'),
('wed_10am', 'Wednesday', '10:00 AM', 15, 'Wed 10:00 AM'),
('wed_11am', 'Wednesday', '11:00 AM', 16, 'Wed 11:00 AM'),
('wed_1pm', 'Wednesday', '1:00 PM', 17, 'Wed 1:00 PM'),
('wed_2pm', 'Wednesday', '2:00 PM', 18, 'Wed 2:00 PM'),
('wed_3pm', 'Wednesday', '3:00 PM', 19, 'Wed 3:00 PM'),
('wed_4pm', 'Wednesday', '4:00 PM', 20, 'Wed 4:00 PM'),
('thu_9am', 'Thursday', '9:00 AM', 21, 'Thu 9:00 AM'),
('thu_10am', 'Thursday', '10:00 AM', 22, 'Thu 10:00 AM'),
('thu_11am', 'Thursday', '11:00 AM', 23, 'Thu 11:00 AM'),
('thu_1pm', 'Thursday', '1:00 PM', 24, 'Thu 1:00 PM'),
('thu_2pm', 'Thursday', '2:00 PM', 25, 'Thu 2:00 PM'),
('thu_3pm', 'Thursday', '3:00 PM', 26, 'Thu 3:00 PM'),
('thu_4pm', 'Thursday', '4:00 PM', 27, 'Thu 4:00 PM'),
('fri_9am', 'Friday', '9:00 AM', 28, 'Fri 9:00 AM'),
('fri_10am', 'Friday', '10:00 AM', 29, 'Fri 10:00 AM'),
('fri_11am', 'Friday', '11:00 AM', 30, 'Fri 11:00 AM'),
('fri_1pm', 'Friday', '1:00 PM', 31, 'Fri 1:00 PM'),
('fri_2pm', 'Friday', '2:00 PM', 32, 'Fri 2:00 PM'),
('fri_3pm', 'Friday', '3:00 PM', 33, 'Fri 3:00 PM'),
('fri_4pm', 'Friday', '4:00 PM', 34, 'Fri 4:00 PM');
