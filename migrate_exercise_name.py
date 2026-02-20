#!/usr/bin/env python3
"""
Migration script to add exercise_name column to session_exercises table
if it doesn't already exist.
"""

import sqlite3
import sys

def migrate_db(db_path='instance/rehab_app.db'):
    """Add exercise_name column to session_exercises table if it doesn't exist."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(session_exercises)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'exercise_name' in columns:
            print("✅ Column 'exercise_name' already exists in session_exercises table")
            conn.close()
            return True
        
        # Add the column if it doesn't exist
        print("Adding 'exercise_name' column to session_exercises table...")
        cursor.execute("""
            ALTER TABLE session_exercises
            ADD COLUMN exercise_name TEXT DEFAULT ''
        """)
        
        conn.commit()
        print("✅ Successfully added 'exercise_name' column")
        
        # Verify
        cursor.execute("PRAGMA table_info(session_exercises)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Current columns: {columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == '__main__':
    db_path = 'instance/rehab_app.db'
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Migrating database: {db_path}")
    if migrate_db(db_path):
        print("✅ Migration completed successfully")
        sys.exit(0)
    else:
        print("❌ Migration failed")
        sys.exit(1)
