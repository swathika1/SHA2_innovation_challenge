"""
Apply database migration for optimization features.
This script safely adds new tables and columns to the existing database.
"""

import sqlite3
import os
import sys

DB_PATH = 'rehab_coach.db'

if not os.path.exists(DB_PATH):
    print(f"❌ Database {DB_PATH} not found!")
    print("   Please run init_database.py first to create the database.")
    sys.exit(1)

print("🔄 Applying database migration for optimization features...")
print("-" * 60)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Read and execute migration script
    with open('schema_migration.sql', 'r') as f:
        migration_sql = f.read()
    
    # Execute each statement (SQLite executescript doesn't support parameterized queries well)
    cursor.executescript(migration_sql)
    conn.commit()
    
    print("✅ Migration completed successfully!")
    print("-" * 60)
    
    # Verify new tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("\n📋 Current database tables:")
    for table in tables:
        print(f"   - {table}")
    
    # Count timeslots
    cursor.execute("SELECT COUNT(*) FROM timeslots")
    count = cursor.fetchone()[0]
    print(f"\n⏰ Total timeslots available: {count}")
    
    print("\n✅ Database is ready for optimization with real data!")
    
except sqlite3.Error as e:
    print(f"❌ Migration failed: {e}")
    conn.rollback()
    sys.exit(1)
finally:
    conn.close()

print("\n" + "=" * 60)
print("Next steps:")
print("  1. Update patient/doctor profiles with optimization data")
print("  2. Run the application: python3 main.py")
print("=" * 60)
