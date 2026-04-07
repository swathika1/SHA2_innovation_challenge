"""
Migrate the rehab condition taxonomy, specialties, and default exercise plans.

This script is idempotent and updates the tracked rehab_coach.db in-place.
"""

import sqlite3
from pathlib import Path


DB_PATH = Path("rehab_coach.db")

MSK_CONDITIONS = [
    "Non-specific Low Back Pain",
    "Lumbar Spondylosis",
    "Cervical Spondylosis",
    "Mechanical Neck Pain",
    "Rotator Cuff Tendinopathy",
    "Shoulder Impingement Syndrome",
    "Knee Osteoarthritis",
    "Patellofemoral Pain Syndrome",
    "Hip Osteoarthritis",
    "Post-Total Knee Replacement (TKR)",
    "Post-Total Hip Replacement (THR)",
    "Post-Shoulder Surgery",
    "Post-Stroke Rehabilitation",
    "Parkinsonian Gait Disorder",
    "Deconditioning Syndrome",
]

DOCTOR_SPECIALTIES = [
    "Physiotherapy (MSK)",
    "Orthopaedic Surgery",
    "Sports Medicine",
    "Neurological Rehabilitation",
    "Geriatric Rehabilitation",
]

DEFAULT_CONDITION = "Deconditioning Syndrome"
DEFAULT_DOCTOR_SPECIALTY = "Physiotherapy (MSK)"

CONDITION_EXERCISE_MAP = {
    "Non-specific Low Back Pain": [
        "Lateral Trunk Tilt",
        "Trunk Rotation",
        "Forward Flexion",
        "Flank Stretch",
    ],
    "Lumbar Spondylosis": [
        "Lateral Trunk Tilt",
        "Trunk Rotation",
        "Flank Stretch",
    ],
    "Cervical Spondylosis": [
        "Lifting of Arms",
        "Trunk Rotation",
    ],
    "Mechanical Neck Pain": [
        "Lifting of Arms",
        "Trunk Rotation",
    ],
    "Rotator Cuff Tendinopathy": [
        "Lifting of Arms",
        "Trunk Rotation",
    ],
    "Shoulder Impingement Syndrome": [
        "Lifting of Arms",
    ],
    "Knee Osteoarthritis": [
        "Squat",
        "Pelvis Rotation",
    ],
    "Patellofemoral Pain Syndrome": [
        "Squat",
    ],
    "Hip Osteoarthritis": [
        "Squat",
        "Pelvis Rotation",
    ],
    "Post-Total Knee Replacement (TKR)": [
        "Squat",
        "Pelvis Rotation",
    ],
    "Post-Total Hip Replacement (THR)": [
        "Pelvis Rotation",
        "Lifting of Arms",
    ],
    "Post-Shoulder Surgery": [
        "Lifting of Arms",
    ],
    "Post-Stroke Rehabilitation": [
        "Trunk Rotation & Target Touch",
        "Forward Flexion",
    ],
    "Parkinsonian Gait Disorder": [
        "Trunk Rotation",
        "Forward Flexion",
    ],
    "Deconditioning Syndrome": [
        "Lateral Trunk Tilt",
        "Trunk Rotation",
        "Squat",
        "Lifting of Arms",
    ],
}

CONDITION_TO_SPECIALTY_MAP = {
    "Non-specific Low Back Pain": ["Physiotherapy (MSK)"],
    "Lumbar Spondylosis": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Cervical Spondylosis": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Mechanical Neck Pain": ["Physiotherapy (MSK)"],
    "Rotator Cuff Tendinopathy": ["Physiotherapy (MSK)", "Sports Medicine"],
    "Shoulder Impingement Syndrome": ["Physiotherapy (MSK)", "Sports Medicine"],
    "Knee Osteoarthritis": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Patellofemoral Pain Syndrome": ["Physiotherapy (MSK)", "Sports Medicine"],
    "Hip Osteoarthritis": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Post-Total Knee Replacement (TKR)": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Post-Total Hip Replacement (THR)": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Post-Shoulder Surgery": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Post-Stroke Rehabilitation": ["Neurological Rehabilitation"],
    "Parkinsonian Gait Disorder": ["Neurological Rehabilitation"],
    "Deconditioning Syndrome": ["Geriatric Rehabilitation", "Physiotherapy (MSK)"],
}

LEGACY_CONDITION_MAP = {
    "General Rehabilitation": "Deconditioning Syndrome",
    "Spine & MSK": "Non-specific Low Back Pain",
    "Post-Surgical Recovery": "Post-Total Knee Replacement (TKR)",
    "Sports Injury": "Patellofemoral Pain Syndrome",
    "Neurological Rehab": "Post-Stroke Rehabilitation",
    "Orthopaedic Rehab": "Knee Osteoarthritis",
}

LEGACY_DOCTOR_SPECIALTY_MAP = {
    "General Rehabilitation": ["Physiotherapy (MSK)", "Geriatric Rehabilitation"],
    "Spine & MSK": ["Physiotherapy (MSK)"],
    "Post-Surgical Recovery": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "Sports Injury": ["Physiotherapy (MSK)", "Sports Medicine"],
    "Neurological Rehab": ["Neurological Rehabilitation"],
    "Orthopaedic Rehab": ["Physiotherapy (MSK)", "Orthopaedic Surgery"],
    "General": ["Physiotherapy (MSK)"],
}


def normalize_condition_name(condition: str) -> str:
    condition = (condition or "").strip()
    if condition in MSK_CONDITIONS:
        return condition
    return LEGACY_CONDITION_MAP.get(condition, DEFAULT_CONDITION)


def ensure_patient_specialties_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_specialties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            specialty TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES users(id),
            UNIQUE(patient_id, specialty)
        )
        """
    )


def load_exercise_map(cursor: sqlite3.Cursor) -> dict[str, tuple[int, str]]:
    cursor.execute("SELECT id, name, COALESCE(description, '') FROM exercises")
    return {name: (exercise_id, description) for exercise_id, name, description in cursor.fetchall()}


def migrate_patients(cursor: sqlite3.Cursor) -> None:
    exercise_map = load_exercise_map(cursor)
    cursor.execute("SELECT user_id, condition FROM patients ORDER BY user_id")
    patients = cursor.fetchall()

    for patient_id, old_condition in patients:
        condition = normalize_condition_name(old_condition)
        specialties = CONDITION_TO_SPECIALTY_MAP.get(condition, [DEFAULT_DOCTOR_SPECIALTY])
        exercise_names = CONDITION_EXERCISE_MAP.get(condition, CONDITION_EXERCISE_MAP[DEFAULT_CONDITION])

        cursor.execute(
            "UPDATE patients SET condition = ?, specialty_needed = ? WHERE user_id = ?",
            (condition, specialties[0], patient_id),
        )

        cursor.execute("DELETE FROM patient_specialties WHERE patient_id = ?", (patient_id,))
        for specialty in specialties:
            cursor.execute(
                "INSERT OR IGNORE INTO patient_specialties (patient_id, specialty) VALUES (?, ?)",
                (patient_id, specialty),
            )

        cursor.execute("UPDATE patient_exercises SET enabled = 0 WHERE patient_id = ?", (patient_id,))
        cursor.execute("UPDATE workouts SET is_active = 0 WHERE patient_id = ?", (patient_id,))

        for exercise_name in exercise_names:
            exercise_info = exercise_map.get(exercise_name)
            if not exercise_info:
                continue
            exercise_id, description = exercise_info
            cursor.execute(
                """
                INSERT OR IGNORE INTO patient_exercises (patient_id, exercise_id, enabled)
                VALUES (?, ?, 1)
                """,
                (patient_id, exercise_id),
            )
            cursor.execute(
                "UPDATE patient_exercises SET enabled = 1 WHERE patient_id = ? AND exercise_id = ?",
                (patient_id, exercise_id),
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO workouts (
                    patient_id, exercise_id, sets, reps, frequency, instructions, is_active
                ) VALUES (?, ?, 3, 10, 'Daily', ?, 1)
                """,
                (patient_id, exercise_id, description),
            )
            cursor.execute(
                "UPDATE workouts SET is_active = 1 WHERE patient_id = ? AND exercise_id = ?",
                (patient_id, exercise_id),
            )


def migrate_doctors(cursor: sqlite3.Cursor) -> None:
    cursor.execute("SELECT id FROM users WHERE role = 'doctor' ORDER BY id")
    doctor_ids = [row[0] for row in cursor.fetchall()]

    for doctor_id in doctor_ids:
        cursor.execute(
            "SELECT specialty FROM doctor_specialties WHERE doctor_id = ?",
            (doctor_id,),
        )
        current = [row[0] for row in cursor.fetchall()]

        normalized = set()
        for specialty in current:
            if specialty in DOCTOR_SPECIALTIES:
                normalized.add(specialty)
            else:
                normalized.update(LEGACY_DOCTOR_SPECIALTY_MAP.get(specialty, []))

        if not normalized:
            normalized.add(DEFAULT_DOCTOR_SPECIALTY)

        cursor.execute("DELETE FROM doctor_specialties WHERE doctor_id = ?", (doctor_id,))
        for specialty in sorted(normalized):
            cursor.execute(
                "INSERT OR IGNORE INTO doctor_specialties (doctor_id, specialty) VALUES (?, ?)",
                (doctor_id, specialty),
            )


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    ensure_patient_specialties_table(cursor)
    migrate_patients(cursor)
    migrate_doctors(cursor)

    conn.commit()
    conn.close()
    print("Condition taxonomy migration completed.")


if __name__ == "__main__":
    main()
