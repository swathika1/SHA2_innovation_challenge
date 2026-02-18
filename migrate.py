#!/usr/bin/env python3
"""
One-command migration script.
Run this to add optimization features to your database.
"""

import sqlite3
import os
import sys

DB_PATH = 'rehab_coach.db'

def check_flask_running():
    """Check if database is locked (Flask running)."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=1)
        conn.execute("SELECT 1")
        conn.close()
        return False
    except sqlite3.OperationalError as e:
        if "locked" in str(e):
            return True
        return False

def main():
    print("\n" + "="*60)
    print("  DATABASE MIGRATION - OPTIMIZATION FEATURES")
    print("="*60 + "\n")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database not found!")
        print(f"   Looking for: {DB_PATH}")
        print("   Run init_database.py first to create the database.")
        sys.exit(1)
    
    # Check if Flask is running
    if check_flask_running():
        print("⚠️  DATABASE IS LOCKED!")
        print("\n" + "─"*60)
        print("Flask is currently running and using the database.")
        print("\nSTEPS TO FIX:")
        print("  1. Press Ctrl+C in the Flask terminal")
        print("  2. Wait for it to fully stop")
        print("  3. Run this script again: python3 migrate.py")
        print("  4. Then restart Flask: python3 main.py")
        print("─"*60 + "\n")
        sys.exit(1)
    
    print("📝 Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if migration already applied
        cursor.execute("PRAGMA table_info(patients)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'urgency' in columns:
            print("✅ Migration already applied!")
            print("   Columns 'urgency', 'max_distance', etc. already exist.")
            print("\n💡 You can now run: python3 main.py")
            conn.close()
            sys.exit(0)
        
        print("🔧 Applying migration...")
        
        # Read and execute migration
        with open('schema_migration.sql', 'r') as f:
            migration_sql = f.read()
        
        cursor.executescript(migration_sql)
        conn.commit()
        
        print("✅ Database tables created!")
        
        # Count what was added
        cursor.execute("SELECT COUNT(*) FROM timeslots")
        ts_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📊 Migration Summary:")
        print(f"   - Created {len(tables)} tables")
        print(f"   - Added {ts_count} appointment timeslots")
        print(f"   - Added columns to 'patients' table")
        
        print("\n" + "="*60)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\n📝 Next steps:")
        print("   1. Update existing users: python3 update_existing_data.py")
        print("   2. Start Flask: python3 main.py")
        print("   3. Go to /signup and create a new patient")
        print("   4. You'll see the new fields (urgency, distance, pincode)!")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nIf you need help, check MIGRATION_STEPS.txt")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
