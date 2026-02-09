"""
init_database.py - Initialize the SQLite database
Run this script ONCE to create all tables and sample data.

Usage:
    python init_database.py
"""

import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = 'rehab_coach.db'

def init_database():
    """Initialize the database with schema and sample data."""
    
    print("🗄️  Initializing Home Rehab Coach Database...")
    
    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Read and execute schema
    print("📋 Creating tables...")
    with open('schema.sql', 'r') as f:
        schema = f.read()
    
    cursor.executescript(schema)
    conn.commit()
    
    # Update sample users with proper password hashes
    print("🔐 Setting up user passwords...")
    
    # Hash passwords properly
    doctor_hash = generate_password_hash('doctor123')
    patient_hash = generate_password_hash('patient123')
    caregiver_hash = generate_password_hash('care123')
    
    # Update passwords
    cursor.execute('UPDATE users SET password = ? WHERE email = ?', 
                   (doctor_hash, 'dr.smith@clinic.com'))
    cursor.execute('UPDATE users SET password = ? WHERE email IN (?, ?, ?, ?)', 
                   (patient_hash, 'john@email.com', 'maria@email.com', 
                    'robert@email.com', 'emily@email.com'))
    cursor.execute('UPDATE users SET password = ? WHERE email = ?', 
                   (caregiver_hash, 'caregiver@email.com'))
    
    conn.commit()
    
    # Verify setup
    print("\n✅ Database initialized successfully!")
    print("\n📊 Database Summary:")
    
    # Count records in each table
    tables = ['users', 'patients', 'exercises', 'workouts', 'appointments', 
              'doctor_patient', 'caregiver_patient']
    
    for table in tables:
        count = cursor.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f"   {table}: {count} records")
    
    # Show sample logins
    print("\n🔑 Sample Login Credentials:")
    print("   Doctor:    dr.smith@clinic.com / doctor123")
    print("   Patient:   john@email.com / patient123")
    print("   Caregiver: caregiver@email.com / care123")
    
    conn.close()
    print("\n🚀 You can now run: python main.py")

if __name__ == '__main__':
    # Safety check - don't wipe existing data accidentally
    import os
    if os.path.exists(DATABASE):
        print("⚠️  WARNING: Database already exists!")
        print("   Running this will DELETE ALL existing users!")
        confirm = input("   Type 'YES' to continue, anything else to cancel: ")
        if confirm != 'YES':
            print("   Cancelled. Your data is safe.")
            exit(0)
    init_database()
