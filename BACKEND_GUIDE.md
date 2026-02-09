# 🏥 Home Rehab Coach - SQLite Backend Guide

A complete, beginner-friendly guide to convert your Flask app from hardcoded data to SQLite database.

---

## 📁 Recommended Folder Structure

```
SHA2_innovation_challenge/
├── main.py                  # Main Flask app with routes
├── database.py              # Database connection helper
├── schema.sql               # SQL to create all tables
├── rehab_coach.db           # SQLite database file (auto-created)
├── requirements.txt         # Python dependencies
├── static/
│   └── styles.css
└── templates/
    ├── base.html
    ├── landing.html
    ├── login.html           # NEW: Login page
    ├── signup.html          # NEW: Signup page
    ├── role_select.html
    ├── caregiver/
    │   └── dashboard.html
    ├── clinician/
    │   ├── consultation.html
    │   ├── dashboard.html
    │   ├── patient_detail.html
    │   └── plan_editor.html
    └── patient/
        ├── checkin.html
        ├── dashboard.html
        ├── progress.html
        ├── session.html
        └── summary.html
```

---

## 🗄️ PART 1: Database Design

### Tables Overview

| Table | Purpose |
|-------|---------|
| `users` | All users (doctors, patients, caregivers) |
| `patients` | Patient-specific medical info |
| `doctor_patient` | Which doctor manages which patient |
| `caregiver_patient` | Which caregiver monitors which patient |
| `exercises` | Library of all exercises |
| `workouts` | Exercise assignments for patients |
| `sessions` | Completed rehab sessions |
| `appointments` | Scheduled consultations |

---

## 📋 PART 2: SQL CREATE TABLE Statements

Create a file called `schema.sql` with these exact statements:

```sql
-- =============================================
-- schema.sql - Database Schema for Home Rehab Coach
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,   -- Auto-incrementing unique ID
    email TEXT UNIQUE NOT NULL,             -- Login email (must be unique)
    password TEXT NOT NULL,                 -- Hashed password
    name TEXT NOT NULL,                     -- Full name
    role TEXT NOT NULL CHECK(role IN ('doctor', 'patient', 'caregiver')),  -- Role type
    phone TEXT,                             -- Optional phone number
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- When account was created
);

-- =============================================
-- 2. PATIENTS TABLE
-- Medical info for users with role='patient'
-- =============================================
CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,        -- Links to users table
    condition TEXT NOT NULL,                -- e.g., "Knee Replacement", "ACL Reconstruction"
    surgery_date DATE,                      -- Date of surgery
    current_week INTEGER DEFAULT 1,         -- Current week of rehab (1, 2, 3...)
    adherence_rate REAL DEFAULT 0,          -- Percentage (0-100)
    avg_pain_level REAL DEFAULT 0,          -- Average pain (0-10)
    avg_quality_score REAL DEFAULT 0,       -- Average form quality (0-100)
    streak_days INTEGER DEFAULT 0,          -- Consecutive days completed
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================
-- 3. DOCTOR_PATIENT TABLE
-- Maps which doctors manage which patients
-- =============================================
CREATE TABLE doctor_patient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,             -- User ID of doctor
    patient_id INTEGER NOT NULL,            -- User ID of patient
    assigned_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(doctor_id, patient_id)           -- Prevent duplicate assignments
);

-- =============================================
-- 4. CAREGIVER_PATIENT TABLE
-- Maps caregivers to patients they monitor
-- =============================================
CREATE TABLE caregiver_patient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caregiver_id INTEGER NOT NULL,          -- User ID of caregiver
    patient_id INTEGER NOT NULL,            -- User ID of patient
    relationship TEXT,                      -- e.g., "Family Member", "Spouse"
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
    name TEXT NOT NULL,                     -- e.g., "Knee Extension"
    description TEXT,                       -- What the exercise does
    category TEXT NOT NULL,                 -- e.g., "Knee", "Hip", "Shoulder"
    video_url TEXT,                         -- Optional: tutorial video link
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- 6. WORKOUTS TABLE
-- Exercise assignments for each patient
-- =============================================
CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,            -- User ID of patient
    exercise_id INTEGER NOT NULL,           -- Which exercise
    sets INTEGER DEFAULT 3,                 -- Number of sets
    reps INTEGER DEFAULT 10,                -- Reps per set
    hold_time INTEGER DEFAULT 5,            -- Hold time in seconds
    rest_time INTEGER DEFAULT 30,           -- Rest between sets in seconds
    frequency TEXT DEFAULT 'Daily',         -- "Daily", "3x per week", etc.
    rom_target INTEGER,                     -- Range of motion target (degrees)
    instructions TEXT,                      -- Special instructions
    is_active INTEGER DEFAULT 1,            -- 1 = active, 0 = removed from plan
    assigned_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
);

-- =============================================
-- 7. SESSIONS TABLE
-- Records of completed rehab sessions
-- =============================================
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    workout_id INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pain_before INTEGER,                    -- Pain level before (0-10)
    pain_after INTEGER,                     -- Pain level after (0-10)
    effort_level INTEGER,                   -- How hard it felt (1-10)
    quality_score INTEGER,                  -- Form quality (0-100)
    sets_completed INTEGER,
    reps_completed INTEGER,
    notes TEXT,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);

-- =============================================
-- 8. APPOINTMENTS TABLE
-- Scheduled video consultations
-- =============================================
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TEXT NOT NULL,         -- e.g., "10:00 AM"
    duration INTEGER DEFAULT 30,            -- Duration in minutes
    status TEXT DEFAULT 'scheduled' CHECK(status IN ('scheduled', 'completed', 'cancelled')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
);

-- =============================================
-- INSERT SAMPLE DATA
-- =============================================

-- Sample Exercises
INSERT INTO exercises (name, description, category) VALUES
('Knee Extension', 'Seated leg raises to strengthen quadriceps', 'Knee'),
('Hip Flexor Stretch', 'Stretching hip flexors for improved mobility', 'Hip'),
('Quad Strengthening', 'Resistance-based quadriceps exercises', 'Knee'),
('Hamstring Curl', 'Lying hamstring curls for balance', 'Knee'),
('Calf Raises', 'Standing calf raises for lower leg strength', 'Knee'),
('Wall Slides', 'Back against wall squatting motion', 'Knee'),
('Shoulder Rotation', 'Gentle shoulder rotation exercises', 'Shoulder'),
('Back Extension', 'Lying back extension for spine mobility', 'Back');
```

---

## 🔧 PART 3: Creating Tables with DB Browser for SQLite

### Step-by-Step Instructions:

1. **Open DB Browser for SQLite**
2. **Create New Database**
   - Click "New Database"
   - Navigate to your project folder: `SHA2_innovation_challenge/`
   - Name it: `rehab_coach.db`
   - Click "Save"

3. **Execute the SQL Schema**
   - Click the "Execute SQL" tab
   - Copy ALL the SQL from `schema.sql` above
   - Paste it into the SQL editor
   - Click the "▶ Execute" button (or press F5)

4. **Verify Tables Created**
   - Click the "Database Structure" tab
   - You should see all 8 tables listed
   - Click on each table to see its columns

5. **Save Changes**
   - Click "Write Changes" (Ctrl+S)

---

## 🔌 PART 4: Flask ↔ SQLite Connection

### Create `database.py`:

```python
"""
database.py - Database connection helper for Flask
Place this file in your project root alongside main.py
"""

import sqlite3
from flask import g

DATABASE = 'rehab_coach.db'  # Database file in same folder

def get_db():
    """
    Get database connection for current request.
    Uses Flask's 'g' object to store connection per-request.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        # Return rows as dictionaries (access by column name)
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """
    Close database connection at end of request.
    Called automatically by Flask.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    """
    Initialize database with schema.
    Call this once when setting up the app.
    """
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.executescript(f.read())
        db.commit()
        print("Database initialized!")

def query_db(query, args=(), one=False):
    """
    Helper function to query database.
    
    Args:
        query: SQL query string
        args: Tuple of parameters for the query
        one: If True, return single row; if False, return all rows
    
    Returns:
        Single row dict or list of row dicts
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv
```

### Understanding the Code:

| Function | What It Does |
|----------|--------------|
| `get_db()` | Opens connection to SQLite. Stores it in Flask's `g` object so the same connection is reused during a request. |
| `close_db()` | Closes the connection when request ends. Prevents memory leaks. |
| `g.db.row_factory = sqlite3.Row` | Makes query results accessible by column name like `row['email']` instead of `row[0]`. |
| `query_db()` | Helper to run SELECT queries easily. |

---

## 🔐 PART 5: Authentication (Signup, Login, Sessions)

### Password Hashing

**IMPORTANT**: Never store passwords as plain text! Use `werkzeug.security`:

```python
from werkzeug.security import generate_password_hash, check_password_hash

# When user signs up - HASH the password before storing
hashed = generate_password_hash('user_password')

# When user logs in - CHECK if password matches
is_valid = check_password_hash(stored_hash, 'attempted_password')
```

---

## 📝 PART 6: Example SQL Operations

### INSERT - Adding a New User

```python
def create_user(email, password, name, role):
    """
    Create a new user in the database.
    
    Example:
        create_user('john@email.com', 'secret123', 'John Smith', 'patient')
    """
    db = get_db()
    
    # Hash the password before storing
    hashed_password = generate_password_hash(password)
    
    # INSERT statement with placeholders (?)
    # NEVER put values directly in the SQL string (SQL injection risk!)
    db.execute(
        'INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)',
        (email, hashed_password, name, role)
    )
    
    # MUST call commit() to save changes
    db.commit()
```

**Line-by-line explanation:**
- `db = get_db()` - Get database connection
- `generate_password_hash(password)` - Convert plain password to secure hash
- `'INSERT INTO users ...'` - SQL command to add new row
- `(?, ?, ?, ?)` - Placeholders for values (prevents SQL injection)
- `(email, hashed_password, name, role)` - Values to insert (in order)
- `db.commit()` - Save changes to database (REQUIRED for INSERT/UPDATE/DELETE)

---

### SELECT - Fetching Data

```python
def get_user_by_email(email):
    """
    Find a user by their email address.
    Returns None if not found.
    """
    db = get_db()
    
    # Execute SELECT query
    user = db.execute(
        'SELECT * FROM users WHERE email = ?',
        (email,)  # NOTE: Single value tuple needs trailing comma!
    ).fetchone()  # fetchone() returns single row or None
    
    return user
```

```python
def get_patients_for_doctor(doctor_id):
    """
    Get all patients assigned to a specific doctor.
    Uses JOIN to combine data from multiple tables.
    """
    db = get_db()
    
    patients = db.execute('''
        SELECT 
            u.id, u.name, u.email,
            p.condition, p.current_week, p.adherence_rate, p.avg_pain_level
        FROM users u
        JOIN patients p ON u.id = p.user_id
        JOIN doctor_patient dp ON u.id = dp.patient_id
        WHERE dp.doctor_id = ?
        ORDER BY u.name
    ''', (doctor_id,)).fetchall()
    
    return patients
```

**Line-by-line explanation:**
- `SELECT ... FROM users u` - Get columns from users table (alias as 'u')
- `JOIN patients p ON u.id = p.user_id` - Combine with patients table where IDs match
- `JOIN doctor_patient dp ON ...` - Also combine with mapping table
- `WHERE dp.doctor_id = ?` - Filter to only this doctor's patients
- `ORDER BY u.name` - Sort alphabetically
- `.fetchall()` - Get all matching rows as a list

---

### UPDATE - Modifying Data

```python
def update_patient_stats(patient_user_id, adherence, pain, quality):
    """
    Update a patient's statistics.
    
    Example:
        update_patient_stats(5, 85.5, 3.2, 78)
    """
    db = get_db()
    
    db.execute('''
        UPDATE patients 
        SET adherence_rate = ?,
            avg_pain_level = ?,
            avg_quality_score = ?
        WHERE user_id = ?
    ''', (adherence, pain, quality, patient_user_id))
    
    db.commit()  # Don't forget to commit!
```

---

### DELETE - Removing Data

```python
def cancel_appointment(appointment_id):
    """
    Delete an appointment from the database.
    """
    db = get_db()
    
    db.execute('DELETE FROM appointments WHERE id = ?', (appointment_id,))
    db.commit()
```

---

## 🗓️ PART 7: Appointments

### Schedule an Appointment

```python
def schedule_appointment(doctor_id, patient_id, date, time, duration, notes=''):
    """
    Create a new appointment.
    
    Example:
        schedule_appointment(1, 5, '2026-02-10', '10:00 AM', 30, 'Follow-up')
    """
    db = get_db()
    
    db.execute('''
        INSERT INTO appointments 
        (doctor_id, patient_id, appointment_date, appointment_time, duration, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (doctor_id, patient_id, date, time, duration, notes))
    
    db.commit()
```

### Get Appointments for a User

```python
def get_appointments_for_doctor(doctor_id):
    """Get all upcoming appointments for a doctor."""
    db = get_db()
    
    return db.execute('''
        SELECT 
            a.*,
            u.name as patient_name
        FROM appointments a
        JOIN users u ON a.patient_id = u.id
        WHERE a.doctor_id = ? 
        AND a.status = 'scheduled'
        AND a.appointment_date >= DATE('now')
        ORDER BY a.appointment_date, a.appointment_time
    ''', (doctor_id,)).fetchall()

def get_appointments_for_patient(patient_id):
    """Get all upcoming appointments for a patient."""
    db = get_db()
    
    return db.execute('''
        SELECT 
            a.*,
            u.name as doctor_name
        FROM appointments a
        JOIN users u ON a.doctor_id = u.id
        WHERE a.patient_id = ?
        AND a.status = 'scheduled'
        ORDER BY a.appointment_date, a.appointment_time
    ''', (patient_id,)).fetchall()
```

---

## 🏋️ PART 8: Workouts

### Assign Exercise to Patient

```python
def assign_workout(patient_id, exercise_id, sets, reps, frequency, instructions=''):
    """
    Assign an exercise to a patient's rehab plan.
    """
    db = get_db()
    
    db.execute('''
        INSERT INTO workouts 
        (patient_id, exercise_id, sets, reps, frequency, instructions)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (patient_id, exercise_id, sets, reps, frequency, instructions))
    
    db.commit()

def get_patient_workouts(patient_id):
    """
    Get all active exercises for a patient.
    """
    db = get_db()
    
    return db.execute('''
        SELECT 
            w.*,
            e.name as exercise_name,
            e.description,
            e.category
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.patient_id = ? AND w.is_active = 1
    ''', (patient_id,)).fetchall()
```

---

## ✅ PART 9: Complete Updated main.py

See the `main.py` file that I've updated with all the database integration!

---

## 🧪 Testing Your Database

### Quick Test Script

Create a file called `test_db.py`:

```python
"""
test_db.py - Test your database setup
Run this to verify everything works!
"""

import sqlite3

def test_database():
    # Connect to database
    conn = sqlite3.connect('rehab_coach.db')
    conn.row_factory = sqlite3.Row
    
    print("✅ Connected to database!")
    
    # Check tables exist
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    
    print(f"\n📋 Tables found: {len(tables)}")
    for table in tables:
        print(f"   - {table['name']}")
    
    # Check exercises were inserted
    exercises = conn.execute("SELECT * FROM exercises").fetchall()
    print(f"\n🏋️ Exercises in library: {len(exercises)}")
    for ex in exercises:
        print(f"   - {ex['name']} ({ex['category']})")
    
    conn.close()
    print("\n✅ All tests passed!")

if __name__ == '__main__':
    test_database()
```

Run it: `python test_db.py`

---

## 📌 Quick Reference

### Common SQL Patterns

| Operation | SQL Pattern |
|-----------|-------------|
| Insert | `INSERT INTO table (col1, col2) VALUES (?, ?)` |
| Select all | `SELECT * FROM table` |
| Select with filter | `SELECT * FROM table WHERE column = ?` |
| Update | `UPDATE table SET column = ? WHERE id = ?` |
| Delete | `DELETE FROM table WHERE id = ?` |
| Join tables | `SELECT * FROM t1 JOIN t2 ON t1.id = t2.foreign_id` |

### Remember!

1. **Always use `?` placeholders** - Never put variables directly in SQL strings
2. **Always `commit()` after INSERT/UPDATE/DELETE** - Changes won't save otherwise
3. **Use `fetchone()` for single row, `fetchall()` for multiple rows**
4. **Close connections** - Use the `close_db()` pattern with Flask's teardown
5. **Hash passwords** - Never store plain text passwords
