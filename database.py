"""
database.py - Database helper functions for Home Rehab Coach
Uses SQLite with Flask's application context
"""

import sqlite3
import math
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


def _haversine(lat1, lon1, lat2, lon2):
    """Return distance in km between two (lat, lon) points using Haversine."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_postal_coords(pincode):
    """
    Look up (lat, lon) for a Singapore postal code from the sg_postal table.
    Returns (lat, lon) tuple or None if not found.
    """
    if not pincode:
        return None
    pc = ''.join(filter(str.isdigit, str(pincode)))
    if not pc:
        return None
    row = query_db(
        'SELECT lat, lon FROM sg_postal WHERE postal_code = ? LIMIT 1',
        (pc,), one=True
    )
    if row:
        return (float(row['lat']), float(row['lon']))
    return None


def calculate_pincode_distance(pincode1, pincode2):
    """
    Calculate distance in km between two Singapore postal codes
    using their lat/lon from the sg_postal table (Haversine formula).

    Falls back to 15.0 km if either postal code is not found.
    """
    coords1 = _get_postal_coords(pincode1)
    coords2 = _get_postal_coords(pincode2)

    if coords1 and coords2:
        dist = _haversine(coords1[0], coords1[1], coords2[0], coords2[1])
        return round(dist, 2)

    # Fallback if postal code not in sg_postal
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
            # Primary: users.pincode, Fallback: patients.address
            patient_user_row = query_db(
                'SELECT pincode FROM users WHERE id = ?',
                (pat_row['id'],), one=True
            )
            patient_pincode = (patient_user_row['pincode'] if patient_user_row and patient_user_row['pincode']
                               else (pat_row['address'] if pat_row['address'] else None))
            
            for doc in doctors:
                # Primary: users.pincode for the doctor, Fallback: doctor_locations.address
                doc_user_row = query_db(
                    'SELECT pincode FROM users WHERE id = ?',
                    (int(doc['id']),), one=True
                )
                doctor_pincode = (doc_user_row['pincode'] if doc_user_row and doc_user_row['pincode']
                                  else (doc.get('clinic_address') if doc.get('clinic_address') else None))
                
                # Calculate real Haversine distance from postal-code lat/lon
                distances[doc['id']] = calculate_pincode_distance(patient_pincode, doctor_pincode)
            
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
