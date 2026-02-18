# Quick Start: Migrating from Synthetic to Real Data

## 🚀 Quick Migration (3 Steps)

If you have an existing database with users:

```bash
# Step 1: Apply schema changes
python3 apply_migration.py

# Step 2: Update existing records
python3 update_existing_data.py

# Step 3: Start the app
python3 main.py
```

If starting fresh:

```bash
# Step 1: Initialize database
python3 init_database.py --reset

# Step 2: Apply migration
python3 apply_migration.py

# Step 3: Start the app
python3 main.py
```

## ✅ What's Changed

- ❌ **REMOVED**: Synthetic datasets in `Optim_dataset/`
- ❌ **REMOVED**: `build_demo_data()` function calls
- ✅ **ADDED**: Real database connections for optimization
- ✅ **ADDED**: Patient urgency, distance, and availability fields
- ✅ **ADDED**: Doctor specialties and availability
- ✅ **ADDED**: 35 appointment timeslots (Mon-Fri, 9am-4pm)

## 📝 How to Use

### As a Patient:

1. **Sign up** at `/signup`
   - Select role: "Patient"
   - Fill in medical condition
   - Choose appointment urgency (Low/Medium/High)
   - Set max travel distance
   - Enter your address

2. **Login** and go to "Consultations"

3. **Click "Get My Best Appointment Options"**
   - System loads YOUR real data from database
   - Runs optimization algorithm
   - Returns personalized doctor recommendations

### As a Doctor:

1. **Sign up** at `/signup`
   - Select role: "Doctor / Clinician"
   - Select your specialties (MSK, Post-op, Neuro, etc.)
   - Enter clinic name and address
   - System sets you as available for all timeslots by default

2. **Login** and go to dashboard
   - View patient optimization results
   - See matched patients based on specialty and urgency

## 🧪 Testing

Create test accounts to verify:

```python
# Test Patient 1: High urgency, close distance
Email: patient1@test.com
Urgency: High
Condition: Knee Replacement (→ Post-op specialty)
Max Distance: 10 km

# Test Patient 2: Low urgency, any distance
Email: patient2@test.com
Urgency: Low
Condition: General Rehab
Max Distance: 50 km

# Test Doctor 1: Post-op specialist
Email: doctor1@test.com
Specialties: [Post-op, MSK]
Clinic: Downtown Rehab Center

# Test Doctor 2: General practitioner
Email: doctor2@test.com
Specialties: [General]
Clinic: Community Health Center
```

Login as patient1@test.com → Appointments → Get Recommendations
- Should prioritize Post-op specialists
- Should show nearby doctors first
- Should show early timeslots (higher urgency)

## 📊 Verification

Check that data is loading correctly:

```sql
-- View all timeslots
SELECT * FROM timeslots LIMIT 5;

-- View patient optimization data
SELECT u.name, p.urgency, p.max_distance, p.specialty_needed
FROM users u
JOIN patients p ON u.id = p.user_id
WHERE u.role = 'patient';

-- View doctor specialties
SELECT u.name, GROUP_CONCAT(ds.specialty) as specialties
FROM users u
JOIN doctor_specialties ds ON u.id = ds.doctor_id
WHERE u.role = 'doctor'
GROUP BY u.name;

-- Check availability counts
SELECT COUNT(*) FROM patient_availability;
SELECT COUNT(*) FROM doctor_availability;
```

## 🔧 Customization

**Change default time preferences:**

Edit `main.py`, signup route, around line 250:

```python
# Change from morning-preferred to afternoon-preferred
is_afternoon = '_1pm' in ts['id'] or '_2pm' in ts['id']
pref_score = 0.9 if is_afternoon else 0.4
```

**Add weekend timeslots:**

Edit `schema_migration.sql`:

```sql
INSERT INTO timeslots (id, day, time, time_index, label) VALUES
('sat_9am', 'Saturday', '9:00 AM', 35, 'Sat 9:00 AM'),
('sat_10am', 'Saturday', '10:00 AM', 36, 'Sat 10:00 AM');
```

Then re-run:
```bash
python3 apply_migration.py
python3 update_existing_data.py
```

## ⚠️ Important Notes

1. **Synthetic datasets are NO LONGER USED**
   - `Optim_dataset/converted_data_*.json` files are NOT loaded
   - All optimization now uses real DB data
   - You can delete these files if desired

2. **New users automatically get optimization data**
   - Signup form collects all needed fields
   - Default availability and preferences are set
   - No manual data entry required

3. **Distance calculations**
   - Currently uses default 10km if lat/long not available
   - To enable real distances, add geocoding service
   - Or manually populate latitude/longitude in DB

## 🐛 Troubleshooting

**"Optimization module not available"**
- Make sure `optim.py` exists
- Check that Gurobi is installed: `pip install gurobipy`

**"Patient not found in system"**
- Patient may not have completed signup
- Run `update_existing_data.py` for old users
- Check that timeslots table is populated

**No recommendations returned**
- Verify doctors have matching specialties
- Check patient max_distance isn't too restrictive
- Ensure doctor availability overlaps with patient availability

**Import errors after migration**
- Restart Flask app: `Ctrl+C` then `python3 main.py`
- Clear Python cache: `rm -rf __pycache__`

## 📚 Files Modified

- ✅ `database.py` - Added optimization data loaders
- ✅ `main.py` - Updated to use real data
- ✅ `templates/signup.html` - Added optimization fields
- ✅ `schema_migration.sql` - New tables and columns
- ✅ `apply_migration.py` - Migration script
- ✅ `update_existing_data.py` - Update old records

## 🎯 Success Criteria

✅ Can register new patients with optimization data  
✅ Can register new doctors with specialties  
✅ Optimization API returns results from real DB  
✅ Patient recommendations use actual user data  
✅ No references to synthetic dataset files  
✅ Distance calculations work (default or real)  

---

**Ready to migrate?** Run `python3 apply_migration.py` to begin!
