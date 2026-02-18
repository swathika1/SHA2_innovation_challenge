#!/usr/bin/env python3
"""Test script to debug optimization data loading"""

from database import load_optimization_data, query_db

print("\n" + "="*80)
print("TESTING OPTIMIZATION DATA LOADING")
print("="*80)

# Load data
patients, doctors, timeslots = load_optimization_data()

print(f"\n✓ Loaded {len(patients)} patients")
print(f"✓ Loaded {len(doctors)} doctors")
print(f"✓ Loaded {len(timeslots)} timeslots")

if not patients:
    print("\n❌ ERROR: No patients found!")
    print("Check that at least one patient is registered.")
    exit(1)

if not doctors:
    print("\n❌ ERROR: No doctors found!")
    print("Check that at least one doctor is registered.")
    exit(1)

if not timeslots:
    print("\n❌ ERROR: No timeslots found!")
    print("Database initialization may have failed.")    
    exit(1)

# Check first patient
patient = patients[0]
print(f"\n📋 FIRST PATIENT: {patient['label']} (ID: {patient['id']})")
print(f"   - Specialty needed: {patient.get('specialty_need')}")
print(f"   - Max distance: {patient.get('max_dist')}km")
print(f"   - Urgency: {patient.get('urgency')}")

avail_slots = sum(1 for v in patient.get('availability', {}).values() if v == 1)
print(f"   - Available slots: {avail_slots}/{len(timeslots)}")

time_prefs = patient.get('time_preference', {})
print(f"   - Time preferences: {len(time_prefs)}")

distances = patient.get('distances', {})
print(f"   - Doctor distances: {distances}")

# Check first doctor  
doctor = doctors[0]
print(f"\n👨‍⚕️ FIRST DOCTOR: {doctor['label']} (ID: {doctor['id']})")
print(f"   - Specialties: {doctor.get('specialties')}")
print(f"   - Clinic address: {doctor.get('clinic_address')}")

doc_avail = sum(1 for v in doctor.get('availability', {}).values() if v == 1)
print(f"   - Available slots: {doc_avail}/{len(timeslots)}")

# Check feasibility
print(f"\n🔍 FEASIBILITY CHECK:")
feasible_pairs = 0
for p in patients:
    for d in doctors:
        dist = p.get('distances', {}).get(d['id'], 999)
        max_dist = p.get('max_dist', 20)
        
        if dist <= max_dist:
            # Check specialty
            need = p.get('specialty_need', 'General')
            has_match = (
                not need or 
                need == 'General' or 
                'General' in d.get('specialties', []) or 
                need in d.get('specialties', [])
            )
            
            if has_match:
                # Check if they have overlapping availability
                for t_id in timeslots:
                    p_avail = p.get('availability', {}).get(t_id['id'], 1)
                    d_avail = d.get('availability', {}).get(t_id['id'], 1)
                    if p_avail == 1 and d_avail == 1:
                        feasible_pairs += 1
                        print(f"   ✓ {p['label']} can see {d['label']} at {p.get('label')} "
                              f"dist={dist}km at {t_id['label']}")
                        break

if feasible_pairs == 0:
    print("   ❌ NO FEASIBLE PATIENT-DOCTOR PAIRS FOUND!")
    print("   Checking why...")
    
    patient = patients[0]
    doctor = doctors[0]
    
    dist = patient.get('distances', {}).get(doctor['id'], 999)
    print(f"\n   Distance from {patient['label']} to {doctor['label']}: {dist}km")
    print(f"   Patient max_dist: {patient.get('max_dist')}km")
    print(f"   Within range: {dist <= patient.get('max_dist', 20)}")
    
    need = patient.get('specialty_need')
    spec = doctor.get('specialties')
    print(f"\n   Patient needs: {need}")
    print(f"   Doctor has: {spec}")
    match = (not need or need == 'General' or 'General' in spec or need in spec)
    print(f"   Specialty match: {match}")
    
    p_avail_count = sum(1 for v in patient.get('availability', {}).values() if v == 1)
    d_avail_count = sum(1 for v in doctor.get('availability', {}).values() if v == 1)
    print(f"\n   Patient available slots: {p_avail_count}/{len(timeslots)}")
    print(f"   Doctor available slots: {d_avail_count}/{len(timeslots)}")
else:
    print(f"   ✓ Found {feasible_pairs} feasible patient-doctor-slot combinations")

print("\n" + "="*80)
