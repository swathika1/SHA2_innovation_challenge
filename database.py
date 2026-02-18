"""
database.py - Database helper functions for Home Rehab Coach
Uses SQLite with Flask's application context
"""

import sqlite3
from flask import g

DATABASE = 'rehab_coach.db'


def get_db():
    """Get database connection for current request context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Execute a SELECT query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute an INSERT/UPDATE/DELETE query and return lastrowid."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    lastrowid = cur.lastrowid
    cur.close()
    return lastrowid


def calculate_pincode_distance(pincode1, pincode2):
    """
    Calculate distance in km between two pincodes using dynamic calculation.
    
    Approach: Use pincode similarity levels + numerical distance
    - Same pincode: ~0.5km
    - First 5 digits match: ~1-2km based on exact difference
    - First 4 digits match: ~2-8km based on exact difference
    - First 3 digits match: ~8-25km based on exact difference
    - First 2 digits match: ~25-60km
    - Otherwise: 100+ km
    """
    try:
        # Extract digits only
        p1 = ''.join(filter(str.isdigit, str(pincode1)))
        p2 = ''.join(filter(str.isdigit, str(pincode2)))
        
        # Pad to 6 digits
        p1 = p1.ljust(6, '0')[:6]
        p2 = p2.ljust(6, '0')[:6]
        
        if not p1 or not p2:
            return 15.0
        
        # Exact match
        if p1 == p2:
            return 0.5
        
        # Calculate numeric difference
        diff = abs(int(p1) - int(p2))
        
        # Check digit-by-digit similarity
        if p1[:6] == p2[:6]:
            # Impossible, but just in case
            return 0.5
        elif p1[:5] == p2[:5]:
            # Last digit differs - very close (same postal region)
            # Map last digit difference (0-9) to 0.5-2km
            return 0.5 + (diff * 0.2)  # 0.5 to 2.3km
        elif p1[:4] == p2[:4]:
            # Same sub-region, last 2 digits differ
            # Map to 2-8km range based on difference
            return 2.0 + min(diff * 0.03, 6.0)  # 2 to 8km
        elif p1[:3] == p2[:3]:
            # Same region (first 3 digits), last 3 differ
            # Map to 8-25km range
            return 8.0 + min(diff * 0.05, 17.0)  # 8 to 25km
        elif p1[:2] == p2[:2]:
            # Same major area, first 2 digits match
            # Map to 25-60km range
            return 25.0 + min(diff * 0.08, 35.0)  # 25 to 60km
        else:
            # Different major regions - far apart
            return 100.0 + min(diff * 0.1, 200.0)
    except:
        # Fallback if any error
        return 15.0


def init_db(app):
    """Initialize database with schema."""
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.executescript(f.read())
        db.commit()


# ==================== OPTIMIZATION DATA LOADERS ====================

def load_optimization_data():
    """
    Load real patient, doctor, and timeslot data from database for optimization.
    
    Returns:
        tuple: (patients, doctors, timeslots) in the format expected by optim.py
    """
    try:
        # Load timeslots
        timeslots_rows = query_db('SELECT * FROM timeslots ORDER BY time_index')
        timeslots = [
            {
                'id': row['id'],
                'label': row['label'],
                'time_index': row['time_index']
            }
            for row in timeslots_rows
        ]
        
        print(f"[DB DEBUG] Loaded {len(timeslots)} timeslots")
        if not timeslots:
            print("[DB DEBUG] WARNING: No timeslots found! Database may not be initialized.")
        
        # Load doctors
        doctors_rows = query_db('''
            SELECT u.id, u.name 
            FROM users u 
            WHERE u.role = 'doctor'
        ''')
        
        print(f"[DB DEBUG] Found {len(doctors_rows) if doctors_rows else 0} doctors from users table")
        
        doctors = []
        for doc_row in doctors_rows:
            doc_id = str(doc_row['id'])
            
            # Get specialties
            spec_rows = query_db(
                'SELECT specialty FROM doctor_specialties WHERE doctor_id = ?',
                (doc_row['id'],)
            )
            specialties = [row['specialty'] for row in spec_rows] if spec_rows else []
            
            # Get availability - must be integers
            avail_rows = query_db(
                'SELECT timeslot_id, available FROM doctor_availability WHERE doctor_id = ?',
                (doc_row['id'],)
            )
            availability = {row['timeslot_id']: int(row['available']) for row in avail_rows} if avail_rows else {}
            
            # Default to available for all slots if no preferences set
            if not availability:
                availability = {ts['id']: 1 for ts in timeslots}
            
            # Get clinic info
            location_row = query_db(
                'SELECT clinic_name, address FROM doctor_locations WHERE doctor_id = ?',
                (doc_row['id'],),
                one=True
            )
            clinic_name = location_row['clinic_name'] if location_row else ''
            clinic_address = location_row['address'] if location_row else ''
            
            doctors.append({
                'id': doc_id,
                'label': doc_row['name'],
                'specialties': specialties if specialties else ['General'],
                'clinic_name': clinic_name,
                'clinic_address': clinic_address,
                'availability': availability
            })
        
        print(f"[DB DEBUG] Loaded {len(doctors)} doctors with specialties")
        for d in doctors:
            print(f"[DB DEBUG]   - {d['label']} ({d['specialties']}) at {d['clinic_address']}")
        
        # Load patients
        patients_rows = query_db('''
            SELECT u.id, u.name, p.* 
            FROM users u
            JOIN patients p ON u.id = p.user_id
            WHERE u.role = 'patient'
        ''')
        
        print(f"[DB DEBUG] Found {len(patients_rows) if patients_rows else 0} patients")
        
        patients = []
        for pat_row in patients_rows:
            patient_id = str(pat_row['id'])
            
            # Map urgency
            urgency_map = {'Low': 1, 'Medium': 2, 'High': 3}
            urgency_str = pat_row['urgency'] if pat_row['urgency'] else 'Medium'
            urgency = urgency_map.get(urgency_str, 2)
            
            # Get rehab score (avg_quality_score 0-10)
            score = float(pat_row['avg_quality_score']) if pat_row['avg_quality_score'] else 5.0
            
            # Get availability
            avail_rows = query_db(
                'SELECT timeslot_id, available FROM patient_availability WHERE patient_id = ?',
                (pat_row['id'],)
            )
            availability = {row['timeslot_id']: int(row['available']) for row in avail_rows} if avail_rows else {}
            
            # Default to available for all slots if no preferences set
            if not availability:
                availability = {ts['id']: 1 for ts in timeslots}
            
            # Get time preferences
            pref_rows = query_db(
                'SELECT timeslot_id, preference_score FROM patient_time_preferences WHERE patient_id = ?',
                (pat_row['id'],)
            )
            time_preferences = {row['timeslot_id']: float(row['preference_score']) for row in pref_rows} if pref_rows else {}
            
            # Default preferences if not set
            if not time_preferences:
                time_preferences = {ts['id']: 0.5 for ts in timeslots}
            
            # Get preferred doctor (continuity)
            continuity = {}
            if pat_row['preferred_doctor_id']:
                continuity[str(pat_row['preferred_doctor_id'])] = 1
            
            distances = {}
            patient_pincode = pat_row['address'] if pat_row['address'] else None
            
            for doc in doctors:
                # Get doctor pincode from doctor_locations table
                doc_location = query_db(
                    'SELECT address FROM doctor_locations WHERE doctor_id = ?',
                    (int(doc['id']),),
                    one=True
                )
                doctor_pincode = doc_location['address'] if doc_location and doc_location['address'] else None
                
                # Calculate distance from pincodes
                if patient_pincode and doctor_pincode:
                    # Use dynamic pincode distance calculation
                    distances[doc['id']] = calculate_pincode_distance(patient_pincode, doctor_pincode)
                else:
                    # If pincodes missing, allow match with default distance
                    distances[doc['id']] = 15.0
            
            max_distance = float(pat_row['max_distance']) if pat_row['max_distance'] else 20.0
            specialty_needed = pat_row['specialty_needed'] if pat_row['specialty_needed'] else 'General'
            
            patients.append({
                'id': patient_id,
                'label': pat_row['name'],
                'score': score,
                'urgency': urgency,
                'max_dist': max_distance,
                'distances': distances,
                'specialty_need': specialty_needed,
                'availability': availability,
                'continuity': continuity,
                'time_preference': time_preferences
            })

        
        print(f"\n[DB DEBUG] Loaded optimization data:")
        print(f"  - {len(patients)} patients")
        print(f"  - {len(doctors)} doctors")
        print(f"  - {len(timeslots)} timeslots")
        
        if patients:
            for p in patients:
                avail_count = sum(1 for v in p.get('availability', {}).values() if v == 1)
                print(f"[DB DEBUG] Patient {p['id']} ({p['label']}): "
                      f"specialty_need={p['specialty_need']}, max_dist={p['max_dist']}km, "
                      f"availability={avail_count}/{len(timeslots)}, "
                      f"pincode_distances={p.get('distances', {})}")
        
        if doctors:
            for d in doctors:
                avail_count = sum(1 for v in d.get('availability', {}).values() if v == 1)
                print(f"[DB DEBUG] Doctor {d['id']} ({d['label']}): "
                      f"specialties={d.get('specialties')}, "
                      f"availability={avail_count}/{len(timeslots)}")
        
        return patients, doctors, timeslots
    
    except Exception as e:
        import traceback
        print(f"[DB ERROR] Failed to load optimization data: {e}")
        print(traceback.format_exc())
        return [], [], []


def calculate_distance(pat_lat, pat_lon, doctor_id):
    """
    Calculate distance between patient and doctor based on pincodes.
    
    Args:
        pat_lat: Patient latitude (unused - we use pincode instead)
        pat_lon: Patient longitude (unused)
        doctor_id: Doctor ID
    
    Returns:
        float: Distance in kilometers
    """
    # Get patient pincode from address field
    patient_id = g.get('current_patient_id')  # Set this in calling function
    if patient_id:
        patient = query_db('SELECT address FROM patients WHERE user_id = ?', (int(patient_id),), one=True)
        patient_pincode = patient['address'] if patient and patient['address'] else None
    else:
        patient_pincode = None
    
    # Get doctor pincode from location
    doc_location = query_db(
        'SELECT address FROM doctor_locations WHERE doctor_id = ?',
        (int(doctor_id),),
        one=True
    )
    doctor_pincode = doc_location['address'] if doc_location and doc_location['address'] else None
    
    # If either pincode is missing, return default
    if not patient_pincode or not doctor_pincode:
        return 5.0
    
    # Simple pincode-based distance estimate
    # Assumes pincodes are numeric and first few digits indicate region
    try:
        # Extract numeric part of pincode
        pat_num = ''.join(filter(str.isdigit, str(patient_pincode)))
        doc_num = ''.join(filter(str.isdigit, str(doctor_pincode)))
        
        if not pat_num or not doc_num:
            return 5.0
        
        # Compare first 3 digits (region)
        pat_region = pat_num[:3] if len(pat_num) >= 3 else pat_num
        doc_region = doc_num[:3] if len(doc_num) >= 3 else doc_num
        
        if pat_region == doc_region:
            # Same region - check sub-region (next 2 digits)
            pat_sub = pat_num[:5] if len(pat_num) >= 5 else pat_num
            doc_sub = doc_num[:5] if len(doc_num) >= 5 else doc_num
            
            if pat_sub == doc_sub:
                return 2.0  # Very close (same area)
            else:
                return 8.0  # Same region, different area
        else:
            # Different regions - calculate rough difference
            region_diff = abs(int(pat_region) - int(doc_region))
            # Each region code difference ≈ 50km (rough estimate)
            estimated_km = min(region_diff * 50, 200)  # Cap at 200km
            return float(estimated_km)
    except:
        # If calculation fails, return default
        return 10.0


def load_patient_optimization_data(patient_id):
    """
    Load optimization data for a specific patient.
    
    Args:
        patient_id: Patient user ID
    
    Returns:
        dict: Patient data in optimization format, or None if not found
    """
    patients, doctors, timeslots = load_optimization_data()
    
    # Find the specific patient
    for patient in patients:
        if patient['id'] == str(patient_id):
            return patient, doctors, timeslots
    
    return None, doctors, timeslots
