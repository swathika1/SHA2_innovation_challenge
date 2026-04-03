#!/usr/bin/env python3
"""
migrate_medical_history.py
--------------------------
Adds the Patient Medical History tables to rehab_coach.db.

All six tables are created inside a single transaction — if any
CREATE TABLE statement fails, none of them are committed, leaving
the database in a clean state.

Safe to re-run: uses CREATE TABLE IF NOT EXISTS throughout.
"""

import sqlite3
import os
import sys

DB_PATH = 'rehab_coach.db'


def check_already_migrated(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_conditions'")
    return cursor.fetchone() is not None


def main():
    print("\n" + "=" * 60)
    print("  MIGRATION — PATIENT MEDICAL HISTORY")
    print("=" * 60 + "\n")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at '{DB_PATH}'.")
        print("Run init_database.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if check_already_migrated(cursor):
        print("Migration already applied — 'medical_conditions' table exists.")
        print("Nothing to do.\n")
        conn.close()
        return

    print("Creating medical history tables inside a single transaction...")

    try:
        # BEGIN explicit transaction — all-or-nothing
        conn.execute("BEGIN")

        conn.executescript("""
-- ──────────────────────────────────────────────────────────────────────────
-- medical_conditions  — chronic diseases (e.g. Type 2 Diabetes, Hypertension)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_conditions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    onset_year  INTEGER,
    notes       TEXT,
    -- audit columns
    entry_mode  TEXT    NOT NULL DEFAULT 'self_report'
                        CHECK(entry_mode IN ('self_report', 'clinician')),
    verified    INTEGER NOT NULL DEFAULT 0,
    entered_by  INTEGER,
    verified_by INTEGER,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES users(id),
    FOREIGN KEY (entered_by)  REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

-- ──────────────────────────────────────────────────────────────────────────
-- medical_surgeries  — past surgical procedures
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_surgeries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL,
    procedure    TEXT    NOT NULL,
    surgery_date DATE,
    body_region  TEXT,
    outcome      TEXT,
    notes        TEXT,
    -- audit columns
    entry_mode   TEXT    NOT NULL DEFAULT 'self_report'
                         CHECK(entry_mode IN ('self_report', 'clinician')),
    verified     INTEGER NOT NULL DEFAULT 0,
    entered_by   INTEGER,
    verified_by  INTEGER,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES users(id),
    FOREIGN KEY (entered_by)  REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

-- ──────────────────────────────────────────────────────────────────────────
-- medical_injuries  — past injuries (fractures, sprains, tears, etc.)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_injuries (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           INTEGER NOT NULL,
    body_region          TEXT    NOT NULL,
    injury_description   TEXT,
    related_to_current   INTEGER NOT NULL DEFAULT 0,  -- 1 = same region as current problem
    recovery_complete    INTEGER NOT NULL DEFAULT 0,  -- 1 = fully recovered
    recurrence           INTEGER NOT NULL DEFAULT 0,  -- 1 = this injury happened before
    injury_date          DATE,
    notes                TEXT,
    -- audit columns
    entry_mode           TEXT    NOT NULL DEFAULT 'self_report'
                                 CHECK(entry_mode IN ('self_report', 'clinician')),
    verified             INTEGER NOT NULL DEFAULT 0,
    entered_by           INTEGER,
    verified_by          INTEGER,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES users(id),
    FOREIGN KEY (entered_by)  REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

-- ──────────────────────────────────────────────────────────────────────────
-- medical_medications  — current and past medications
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_medications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL,
    drug_name   TEXT    NOT NULL,
    indication  TEXT,
    active      INTEGER NOT NULL DEFAULT 1,  -- 1 = currently taking, 0 = stopped
    end_date    DATE,                        -- NULL if still active
    -- audit columns
    entry_mode  TEXT    NOT NULL DEFAULT 'self_report'
                        CHECK(entry_mode IN ('self_report', 'clinician')),
    verified    INTEGER NOT NULL DEFAULT 0,
    entered_by  INTEGER,
    verified_by INTEGER,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES users(id),
    FOREIGN KEY (entered_by)  REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

-- ──────────────────────────────────────────────────────────────────────────
-- medical_family_history  — hereditary conditions in immediate family
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medical_family_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER NOT NULL,
    condition   TEXT    NOT NULL,
    relation    TEXT    NOT NULL,  -- e.g. "Mother", "Father", "Sibling"
    notes       TEXT,
    -- audit columns
    entry_mode  TEXT    NOT NULL DEFAULT 'self_report'
                        CHECK(entry_mode IN ('self_report', 'clinician')),
    verified    INTEGER NOT NULL DEFAULT 0,
    entered_by  INTEGER,
    verified_by INTEGER,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id)  REFERENCES users(id),
    FOREIGN KEY (entered_by)  REFERENCES users(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

-- ──────────────────────────────────────────────────────────────────────────
-- patient_risk_cache  — latest computed re-injury risk score per patient
-- Updated by the risk engine whenever medical history or a session is saved.
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS patient_risk_cache (
    patient_id      INTEGER PRIMARY KEY,
    risk_score_raw  REAL,     -- weighted float before rounding (for precision)
    risk_score      INTEGER,  -- min(12, round(raw)) — matches existing 0-12 scale
    risk_level      TEXT,     -- 'green' | 'yellow' | 'orange' | 'red'
    last_computed   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES users(id)
);
        """)

        conn.commit()
        print("All 6 tables created successfully.\n")

    except Exception as e:
        conn.rollback()
        print(f"\nERROR during migration: {e}")
        print("Transaction rolled back — database is unchanged.")
        conn.close()
        sys.exit(1)

    conn.close()

    print("=" * 60)
    print("Migration complete.")
    print("=" * 60)
    print("\nNew tables:")
    print("  medical_conditions")
    print("  medical_surgeries")
    print("  medical_injuries")
    print("  medical_medications")
    print("  medical_family_history")
    print("  patient_risk_cache")
    print("\nRun python3 main.py to start the app.\n")


if __name__ == '__main__':
    main()
