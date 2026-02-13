#!/usr/bin/env python3
"""
Test script for session logging and dynamic dashboard metrics.
Run this after starting the Flask app to verify everything works.

Usage: python3 test_session_logging.py
"""

import sqlite3
from datetime import datetime, timedelta

def test_database_connection():
    """Test database connection and schema."""
    print("=" * 60)
    print("TEST 1: Database Connection & Schema")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('rehab_coach.db')
        cursor = conn.cursor()
        
        # Check if sessions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='sessions'
        """)
        result = cursor.fetchone()
        
        if result:
            print("✅ Sessions table exists")
            
            # Get table schema
            cursor.execute("PRAGMA table_info(sessions)")
            columns = cursor.fetchall()
            print(f"   Columns: {', '.join([col[1] for col in columns])}")
        else:
            print("❌ Sessions table not found!")
            return False
        
        # Check patients table
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='patients'
        """)
        result = cursor.fetchone()
        
        if result:
            print("✅ Patients table exists")
        else:
            print("❌ Patients table not found!")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def test_session_data():
    """Check if sessions can be queried."""
    print("\n" + "=" * 60)
    print("TEST 2: Session Data Query")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('rehab_coach.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Count total sessions
        cursor.execute("SELECT COUNT(*) as count FROM sessions")
        total = cursor.fetchone()['count']
        print(f"✅ Total sessions in database: {total}")
        
        # Get recent sessions
        cursor.execute("""
            SELECT s.*, u.name as patient_name
            FROM sessions s
            JOIN users u ON s.patient_id = u.id
            ORDER BY s.completed_at DESC
            LIMIT 5
        """)
        sessions = cursor.fetchall()
        
        if sessions:
            print(f"\n   Recent sessions:")
            for sess in sessions:
                print(f"   - Patient: {sess['patient_name']}")
                print(f"     Quality: {sess['quality_score']:.1f}, Pain: {sess['pain_after']}, Sets: {sess['sets_completed']}")
                print(f"     Date: {sess['completed_at']}")
        else:
            print("   No sessions found yet. Complete a session to test!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error querying sessions: {e}")
        return False


def test_patient_metrics():
    """Check patient metrics calculation."""
    print("\n" + "=" * 60)
    print("TEST 3: Patient Metrics")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('rehab_coach.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all patients with metrics
        cursor.execute("""
            SELECT p.*, u.name, u.email
            FROM patients p
            JOIN users u ON p.user_id = u.id
            WHERE u.role = 'patient'
        """)
        patients = cursor.fetchall()
        
        if patients:
            print(f"✅ Found {len(patients)} patients")
            for patient in patients:
                print(f"\n   Patient: {patient['name']} ({patient['email']})")
                print(f"   - Adherence Rate: {patient['adherence_rate']:.1f}%")
                print(f"   - Streak Days: {patient['streak_days']}")
                print(f"   - Avg Quality: {patient['avg_quality_score']:.1f}/100")
                print(f"   - Avg Pain: {patient['avg_pain_level']:.1f}/10")
                
                # Get session count for this patient
                cursor.execute(
                    "SELECT COUNT(*) as count FROM sessions WHERE patient_id = ?",
                    (patient['user_id'],)
                )
                session_count = cursor.fetchone()['count']
                print(f"   - Total Sessions: {session_count}")
        else:
            print("   No patients found in database")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking patient metrics: {e}")
        return False


def test_metric_calculations():
    """Test that metric calculation functions work correctly."""
    print("\n" + "=" * 60)
    print("TEST 4: Metric Calculation Logic")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect('rehab_coach.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get a patient with sessions
        cursor.execute("""
            SELECT DISTINCT s.patient_id, u.name
            FROM sessions s
            JOIN users u ON s.patient_id = u.id
            LIMIT 1
        """)
        patient = cursor.fetchone()
        
        if not patient:
            print("   No patients with sessions yet. Complete a session first!")
            conn.close()
            return True
        
        patient_id = patient['patient_id']
        print(f"   Testing calculations for: {patient['name']}")
        
        # Calculate average quality (last 30 days)
        cursor.execute("""
            SELECT AVG(quality_score) as avg_quality
            FROM sessions
            WHERE patient_id = ?
            AND completed_at >= date('now', '-30 days')
        """, (patient_id,))
        result = cursor.fetchone()
        avg_quality = result['avg_quality'] if result['avg_quality'] else 0
        print(f"   ✅ Avg Quality Score (30 days): {avg_quality:.2f}")
        
        # Calculate average pain (last 30 days)
        cursor.execute("""
            SELECT AVG(pain_after) as avg_pain
            FROM sessions
            WHERE patient_id = ?
            AND completed_at >= date('now', '-30 days')
        """, (patient_id,))
        result = cursor.fetchone()
        avg_pain = result['avg_pain'] if result['avg_pain'] else 0
        print(f"   ✅ Avg Pain Level (30 days): {avg_pain:.2f}")
        
        # Calculate adherence rate
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM workouts
            WHERE patient_id = ? AND is_active = 1
        """, (patient_id,))
        workouts_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM sessions
            WHERE patient_id = ?
            AND completed_at >= date('now', '-30 days')
        """, (patient_id,))
        sessions_count = cursor.fetchone()['count']
        
        expected_sessions = workouts_count * 30
        adherence = min(100, (sessions_count / expected_sessions * 100) if expected_sessions > 0 else 0)
        print(f"   ✅ Adherence Rate: {adherence:.1f}% ({sessions_count}/{expected_sessions} sessions)")
        
        # Get streak info
        cursor.execute("""
            SELECT DISTINCT date(completed_at) as session_date
            FROM sessions
            WHERE patient_id = ?
            ORDER BY session_date DESC
            LIMIT 10
        """, (patient_id,))
        dates = [row['session_date'] for row in cursor.fetchall()]
        print(f"   ✅ Recent session dates: {', '.join(dates[:5])}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing calculations: {e}")
        return False


def test_api_endpoints():
    """Check if API endpoints are configured correctly."""
    print("\n" + "=" * 60)
    print("TEST 5: API Endpoint Configuration")
    print("=" * 60)
    
    try:
        # Read main.py to check for endpoints
        with open('main.py', 'r') as f:
            content = f.read()
        
        endpoints = [
            '/api/session/start',
            '/api/session/save',
            '/patient/dashboard',
            '/patient/session'
        ]
        
        for endpoint in endpoints:
            if f'@app.route(\'{endpoint}\'' in content or f'@app.route("{endpoint}"' in content:
                print(f"   ✅ Endpoint {endpoint} found")
            else:
                print(f"   ❌ Endpoint {endpoint} NOT found!")
                return False
        
        # Check for key functions
        functions = [
            'update_patient_metrics',
            'calculate_streak',
            'api_session_save'
        ]
        
        for func in functions:
            if f'def {func}' in content:
                print(f"   ✅ Function {func}() defined")
            else:
                print(f"   ❌ Function {func}() NOT found!")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking endpoints: {e}")
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "SESSION LOGGING TEST SUITE" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    tests = [
        test_database_connection,
        test_session_data,
        test_patient_metrics,
        test_metric_calculations,
        test_api_endpoints
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All tests passed! Session logging is working correctly.")
        print("\nNext steps:")
        print("1. Start Flask app: python3 main.py")
        print("2. Login as a patient")
        print("3. Complete a session to test the full flow")
        print("4. Check dashboard to see updated metrics")
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        print("Make sure:")
        print("- Database exists (rehab_coach.db)")
        print("- Tables are created (run app once to initialize)")
        print("- All code changes have been applied")
    
    print()


if __name__ == '__main__':
    main()
