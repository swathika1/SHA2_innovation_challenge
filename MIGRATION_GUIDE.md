# Database Migration to Real User Data for Optimization

## Overview

This migration removes synthetic dataset dependencies and connects the appointment optimization system to real user data from the registration/login system.

## What Changed

### 1. Database Schema Updates (`schema_migration.sql`)

**New Tables:**
- `timeslots` - Available appointment time slots (Mon-Fri, 9am-5pm)
- `doctor_specialties` - Doctor specialization areas (MSK, Post-op, Neuro, etc.)
- `doctor_availability` - Which timeslots each doctor is available
- `doctor_locations` - Doctor clinic locations for distance calculations
- `patient_availability` - Which timeslots each patient is available
- `patient_time_preferences` - Patient preference scores for each timeslot (0-1)

**New Columns in `patients` table:**
- `urgency` - Appointment urgency level (Low/Medium/High)
- `max_distance` - Maximum distance patient willing to travel (km)
- `specialty_needed` - Required doctor specialty
- `preferred_doctor_id` - Preferred/continuity doctor
- `address`, `latitude`, `longitude` - Location data for distance calculations

### 2. Updated Signup Forms

**Patient Signup now collects:**
- Appointment urgency level
- Maximum travel distance preference
- Address/location
- Medical condition (automatically maps to specialty needed)

**Doctor Signup now collects:**
- Specialties (multiple selections: General, MSK, Post-op, Neuro, Sports, Orthopedic)
- Clinic name and address
- Default availability (all weekday slots)

### 3. Database Functions (`database.py`)

**New Functions:**
- `load_optimization_data()` - Loads all patients, doctors, and timeslots from DB
- `load_patient_optimization_data(patient_id)` - Loads data for specific patient
- `calculate_distance(pat_lat, pat_lon, doctor_id)` - Haversine distance calculation

### 4. Main Application Updates (`main.py`)

**Removed:**
- `build_demo_data()` import and all calls
- `load_dataset()` import and references
- Synthetic data dependencies

**Updated API Endpoints:**
- `/api/optimize/demo` - Now uses real DB data
- `/api/optimize/consultation` - Now uses real DB data  
- `/api/optimize/patient/<id>` - Now uses real DB data
- `/api/patient/recommendations` - Now uses real patient data (no more demo patient mapping)

**Updated Signup Handler:**
- Saves optimization fields for patients (urgency, max_distance, specialty, etc.)
- Creates default availability (all timeslots available)
- Creates time preferences (morning slots preferred by default)
- Saves doctor specialties and location
- Creates doctor availability

## Migration Steps

### Step 1: Apply Database Migration

```bash
python3 apply_migration.py
```

This will:
- Create new tables (timeslots, doctor_specialties, etc.)
- Add new columns to patients table
- Populate 35 default timeslots (Mon-Fri, 9am-4pm)

### Step 2: Update Existing Data (if needed)

If you have existing users, you may need to set default optimization values:

```sql
-- Set default urgency for existing patients
UPDATE patients SET urgency = 'Medium' WHERE urgency IS NULL;

-- Set default max_distance for existing patients
UPDATE patients SET max_distance = 20.0 WHERE max_distance IS NULL;

-- Add default availability for existing patients
INSERT INTO patient_availability (patient_id, timeslot_id, available)
SELECT p.user_id, t.id, 1
FROM patients p
CROSS JOIN timeslots t
WHERE NOT EXISTS (
    SELECT 1 FROM patient_availability pa 
    WHERE pa.patient_id = p.user_id AND pa.timeslot_id = t.id
);

-- Add default time preferences for existing patients
INSERT INTO patient_time_preferences (patient_id, timeslot_id, preference_score)
SELECT p.user_id, t.id, 
    CASE 
        WHEN t.id LIKE '%_9am' OR t.id LIKE '%_10am' OR t.id LIKE '%_11am' THEN 0.8
        ELSE 0.5
    END
FROM patients p
CROSS JOIN timeslots t
WHERE NOT EXISTS (
    SELECT 1 FROM patient_time_preferences ptp 
    WHERE ptp.patient_id = p.user_id AND ptp.timeslot_id = t.id
);

-- Add default specialties for existing doctors
INSERT OR IGNORE INTO doctor_specialties (doctor_id, specialty)
SELECT id, 'General'
FROM users
WHERE role = 'doctor'
AND NOT EXISTS (
    SELECT 1 FROM doctor_specialties ds WHERE ds.doctor_id = users.id
);

-- Add default availability for existing doctors
INSERT INTO doctor_availability (doctor_id, timeslot_id, available)
SELECT u.id, t.id, 1
FROM users u
CROSS JOIN timeslots t
WHERE u.role = 'doctor'
AND NOT EXISTS (
    SELECT 1 FROM doctor_availability da 
    WHERE da.doctor_id = u.id AND da.timeslot_id = t.id
);
```

### Step 3: Test the System

1. **Create new test accounts** using the updated signup form
2. **Login as patient** and go to Appointments page
3. **Click "Get My Best Appointment Options"** to test optimization
4. **Verify** that recommendations are based on real user data

## How It Works Now

### Patient Flow:

1. **Signup** → Patient provides:
   - Urgency level
   - Max travel distance
   - Medical condition
   - Address

2. **Database** → Automatically:
   - Maps condition to specialty needed
   - Creates availability for all timeslots
   - Sets time preferences (morning preferred)
   - Assigns preferred doctor if selected

3. **Appointments Page** → Click "Get Recommendations"
   - Loads patient's real data from DB
   - Loads all doctors with specialties
   - Runs optimization algorithm
   - Returns top 3 personalized recommendations

### Doctor Flow:

1. **Signup** → Doctor provides:
   - Specialties (multiple selections)
   - Clinic name and address
   - Default availability (all slots)

2. **Consultation Page** → View optimization results
   - Loads all patients from DB
   - Runs optimization for all patients
   - Shows best matches based on specialty, distance, urgency

## Benefits of Real Data Integration

✅ **No more synthetic datasets** - All data comes from real user registrations  
✅ **Dynamic updates** - New users immediately available in optimization  
✅ **Personalized results** - Based on actual user preferences and conditions  
✅ **Scalable** - Grows automatically as users register  
✅ **Accurate distances** - Uses real locations (when lat/long available)  
✅ **Better continuity** - Tracks preferred doctors from signup  

## Customization

### Adding/Modifying Timeslots

Edit `schema_migration.sql` to add more timeslots:

```sql
INSERT INTO timeslots (id, day, time, time_index, label) VALUES
('sat_9am', 'Saturday', '9:00 AM', 35, 'Sat 9:00 AM'),
('sat_10am', 'Saturday', '10:00 AM', 36, 'Sat 10:00 AM');
```

### Adding More Specialties

Update `templates/signup.html` in the doctor fields section:

```html
<label style="display: block; margin: 5px 0;">
    <input type="checkbox" name="specialties" value="Pediatric"> Pediatric
</label>
```

### Customizing Default Preferences

Edit the signup handler in `main.py` to change default time preferences:

```python
# Example: Prefer afternoon slots instead
is_afternoon = '_1pm' in ts['id'] or '_2pm' in ts['id'] or '_3pm' in ts['id']
pref_score = 0.9 if is_afternoon else 0.4
```

## Testing Tips

1. **Create multiple test doctors** with different specialties
2. **Create multiple test patients** with different urgencies and conditions
3. **Test edge cases:**
   - Patient with high urgency and low distance
   - Patient needing specific specialty
   - Patient with preferred doctor
   - Doctor with limited availability

## Troubleshooting

**"Patient not found in system" error:**
- Make sure patient has completed signup with all fields
- Check that timeslots table is populated
- Verify patient_availability entries exist

**No recommendations returned:**
- Check doctor_availability - ensure doctors have available slots
- Verify patient max_distance isn't too restrictive
- Check specialty_needed matches doctor specialties

**Distance always shows 10km:**
- Add latitude/longitude to patient and doctor location tables
- Database will use Haversine formula when coordinates available

## Next Steps

1. **Geocoding Service** - Automatically convert addresses to lat/long
2. **Availability Management** - UI for doctors to set/update their availability
3. **Time Preferences UI** - Let patients customize their time slot preferences
4. **Real-time Updates** - WebSocket updates when new recommendations available

---

**Migration Date:** February 18, 2026  
**Status:** ✅ Complete - Ready for production use
