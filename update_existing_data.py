"""
Update existing database records with default optimization values.
Run this AFTER applying schema_migration.sql if you have existing users.
"""

import sqlite3
import os

DB_PATH = 'rehab_coach.db'

if not os.path.exists(DB_PATH):
    print(f"❌ Database {DB_PATH} not found!")
    print("   Please run init_database.py first.")
    exit(1)

print("🔄 Updating existing records with optimization defaults...")
print("-" * 60)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Update existing patients with default values
    print("📝 Setting default urgency and max_distance for existing patients...")
    cursor.execute("UPDATE patients SET urgency = 'Medium' WHERE urgency IS NULL")
    cursor.execute("UPDATE patients SET max_distance = 20.0 WHERE max_distance IS NULL")
    patients_updated = cursor.rowcount
    
    # Map existing conditions to specialties
    print("📝 Mapping conditions to specialty needs...")
    condition_map = {
        'Knee Replacement': 'Post-op',
        'Hip Replacement': 'Post-op',
        'ACL Reconstruction': 'Sports',
        'Shoulder Surgery': 'Post-op',
        'Back Pain': 'MSK',
        'Stroke Recovery': 'Neuro',
        'General Rehab': 'General'
    }
    
    for condition, specialty in condition_map.items():
        cursor.execute(
            "UPDATE patients SET specialty_needed = ? WHERE condition = ? AND specialty_needed IS NULL",
            (specialty, condition)
        )
    
    # Set 'General' for any remaining NULL specialty_needed
    cursor.execute("UPDATE patients SET specialty_needed = 'General' WHERE specialty_needed IS NULL")
    
    # Get list of all timeslots
    cursor.execute("SELECT id FROM timeslots")
    timeslots = [row[0] for row in cursor.fetchall()]
    
    if not timeslots:
        print("⚠️  No timeslots found! Please run apply_migration.py first.")
        conn.close()
        exit(1)
    
    # Add default availability for existing patients
    print(f"📝 Adding availability for {len(timeslots)} timeslots to existing patients...")
    cursor.execute("SELECT user_id FROM patients")
    patients = [row[0] for row in cursor.fetchall()]
    
    avail_count = 0
    for patient_id in patients:
        for timeslot_id in timeslots:
            cursor.execute('''
                INSERT OR IGNORE INTO patient_availability (patient_id, timeslot_id, available)
                VALUES (?, ?, 1)
            ''', (patient_id, timeslot_id))
            if cursor.rowcount > 0:
                avail_count += 1
    
    print(f"   Added {avail_count} availability entries")
    
    # Add default time preferences for existing patients (morning preferred)
    print("📝 Setting time preferences for existing patients...")
    pref_count = 0
    for patient_id in patients:
        for timeslot_id in timeslots:
            is_morning = '_9am' in timeslot_id or '_10am' in timeslot_id or '_11am' in timeslot_id
            pref_score = 0.8 if is_morning else 0.5
            cursor.execute('''
                INSERT OR IGNORE INTO patient_time_preferences (patient_id, timeslot_id, preference_score)
                VALUES (?, ?, ?)
            ''', (patient_id, timeslot_id, pref_score))
            if cursor.rowcount > 0:
                pref_count += 1
    
    print(f"   Added {pref_count} time preference entries")
    
    # Add default specialties for existing doctors
    print("📝 Adding default specialties to existing doctors...")
    cursor.execute("SELECT id FROM users WHERE role = 'doctor'")
    doctors = [row[0] for row in cursor.fetchall()]
    
    spec_count = 0
    for doctor_id in doctors:
        cursor.execute('''
            INSERT OR IGNORE INTO doctor_specialties (doctor_id, specialty)
            VALUES (?, 'General')
        ''', (doctor_id,))
        if cursor.rowcount > 0:
            spec_count += 1
    
    print(f"   Added 'General' specialty to {spec_count} doctors")
    
    # Add default availability for existing doctors
    print("📝 Setting availability for existing doctors...")
    doc_avail_count = 0
    for doctor_id in doctors:
        for timeslot_id in timeslots:
            cursor.execute('''
                INSERT OR IGNORE INTO doctor_availability (doctor_id, timeslot_id, available)
                VALUES (?, ?, 1)
            ''', (doctor_id, timeslot_id))
            if cursor.rowcount > 0:
                doc_avail_count += 1
    
    print(f"   Added {doc_avail_count} availability entries for doctors")
    
    # Add default location entries for doctors
    print("📝 Creating location entries for existing doctors...")
    loc_count = 0
    for doctor_id in doctors:
        cursor.execute('''
            INSERT OR IGNORE INTO doctor_locations (doctor_id, clinic_name, address)
            VALUES (?, 'Main Clinic', '')
        ''', (doctor_id,))
        if cursor.rowcount > 0:
            loc_count += 1
    
    print(f"   Added {loc_count} location entries")
    
    conn.commit()
    
    print("\n" + "=" * 60)
    print("✅ Successfully updated existing records!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - Updated {len(patients)} patients")
    print(f"  - Updated {len(doctors)} doctors")
    print(f"  - Added {avail_count} patient availability entries")
    print(f"  - Added {pref_count} patient time preferences")
    print(f"  - Added {doc_avail_count} doctor availability entries")
    print(f"  - Added {spec_count} doctor specialties")
    print(f"  - Populated across {len(timeslots)} timeslots")
    
    print("\n✅ Database is ready! You can now use real data optimization.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    conn.rollback()
    exit(1)
finally:
    conn.close()
