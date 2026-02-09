"""
test_db.py - Test your database setup
Run this to verify everything works!

Usage:
    python test_db.py
"""

import sqlite3
import os

DATABASE = 'rehab_coach.db'

def test_database():
    """Test the database setup and display summary."""
    
    print("=" * 50)
    print("🧪 Home Rehab Coach - Database Test")
    print("=" * 50)
    
    # Check if database file exists
    if not os.path.exists(DATABASE):
        print(f"\n❌ Database file '{DATABASE}' not found!")
        print("   Run 'python init_database.py' first to create it.")
        return False
    
    print(f"\n✅ Database file found: {DATABASE}")
    
    # Connect to database
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check tables exist
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    
    print(f"\n📋 Tables found: {len(tables)}")
    for table in tables:
        count = cursor.execute(f'SELECT COUNT(*) FROM {table["name"]}').fetchone()[0]
        print(f"   ✓ {table['name']}: {count} records")
    
    # Test: List all users
    print("\n👥 Users in database:")
    users = cursor.execute('SELECT id, name, email, role FROM users').fetchall()
    for user in users:
        print(f"   [{user['id']}] {user['name']} ({user['role']}) - {user['email']}")
    
    # Test: List exercises
    print("\n🏋️ Exercise Library:")
    exercises = cursor.execute('SELECT name, category FROM exercises').fetchall()
    for ex in exercises:
        print(f"   - {ex['name']} ({ex['category']})")
    
    # Test: Doctor-Patient relationships
    print("\n👨‍⚕️ Doctor-Patient Assignments:")
    assignments = cursor.execute('''
        SELECT d.name as doctor, p.name as patient
        FROM doctor_patient dp
        JOIN users d ON dp.doctor_id = d.id
        JOIN users p ON dp.patient_id = p.id
    ''').fetchall()
    for a in assignments:
        print(f"   Dr. {a['doctor']} → {a['patient']}")
    
    # Test: Upcoming appointments
    print("\n📅 Scheduled Appointments:")
    appointments = cursor.execute('''
        SELECT 
            d.name as doctor,
            p.name as patient,
            a.appointment_date,
            a.appointment_time
        FROM appointments a
        JOIN users d ON a.doctor_id = d.id
        JOIN users p ON a.patient_id = p.id
        WHERE a.status = 'scheduled'
    ''').fetchall()
    for appt in appointments:
        print(f"   {appt['appointment_date']} {appt['appointment_time']}: {appt['patient']} with Dr. {appt['doctor']}")
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ All tests passed! Database is ready.")
    print("=" * 50)
    print("\n🚀 Run the app with: python main.py")
    print("   Then visit: http://127.0.0.1:5000")
    print("\n🔑 Login credentials:")
    print("   Doctor:    dr.smith@clinic.com / doctor123")
    print("   Patient:   john@email.com / patient123")
    print("   Caregiver: caregiver@email.com / care123")
    
    return True

if __name__ == '__main__':
    test_database()
