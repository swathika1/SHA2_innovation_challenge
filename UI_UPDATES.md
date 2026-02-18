# UI Updates - Patient Scheduling Preferences

## ✅ What's New

**Added a "Scheduling Preferences" section** to the Patient Appointments page where patients can:

1. **View and Edit Urgency Level**
   - Low - Routine Follow-up
   - Medium - Regular Check-in  
   - High - Need Consultation Soon

2. **Set Maximum Travel Distance**
   - Options: 5km, 10km, 20km, 30km, 50km, or any distance
   - Only shows doctors within this range

3. **Choose Preferred Appointment Times**
   - Morning (9am-12pm)
   - Afternoon (1pm-5pm)
   - Affects which timeslots get higher priority

4. **Update Address**
   - Helps system find nearby doctors
   - Used for distance calculations

## 🎯 How to Use (As Patient)

### Step 1: Login as Patient
Navigate to: `http://localhost:5000/login`

### Step 2: Go to Appointments Page
Click "Consultations" in the navigation menu

### Step 3: Set Your Preferences
1. **Click on "⚙️ My Scheduling Preferences"** (green header at top)
   - Panel will expand showing all preference options
   
2. **Fill in your preferences:**
   - Select urgency level
   - Choose max travel distance
   - Check preferred times (morning/afternoon)
   - Enter your address

3. **Click "💾 Save Preferences"**
   - You'll see a success message
   - Panel will auto-close after 3 seconds

### Step 4: Get Recommendations
1. **Click "🔍 Get My Best Appointment Options"**
   - System loads YOUR real preferences from database
   - Runs optimization algorithm
   - Shows top 3 personalized recommendations

2. **Review Recommendations**
   - Each shows: Doctor name, specialty, timeslot, distance
   - Recommendations are ranked by best match

3. **Book an Appointment**
   - Click "Book" on any recommendation
   - Form auto-fills with doctor, date, and time
   - Click "Request Appointment" to finalize

## 📋 What Fields Are Used in Optimization

The system now uses these real parameters from your preferences:

| Field | How It's Used |
|-------|---------------|
| **Urgency** | High urgency = earlier timeslots prioritized |
| **Max Distance** | Filters out doctors beyond this range |
| **Preferred Times** | Morning/afternoon slots get higher scores |
| **Address** | Calculates distance to each doctor |
| **Specialty Needed** | Matches to doctor specialties (auto-set from condition) |
| **Rehab Score** | Lower scores trigger critical notifications |

## 🔄 How It's Connected to Database

### Frontend → Backend → Database Flow:

1. **User fills preferences form** → Submits via JavaScript `fetch()`

2. **Backend receives request** → `/api/patient/update-preferences` endpoint

3. **Database updates:**
   - `patients` table: urgency, max_distance, address
   - `patient_time_preferences` table: preference scores for each timeslot

4. **User clicks "Get Recommendations"** → Calls `/api/patient/recommendations`

5. **Backend loads real data:**
   - Calls `load_optimization_data()` in `database.py`
   - Loads patient, doctors, timeslots from DB
   - Runs optimization with real parameters
   - Returns personalized recommendations

## 🎨 Visual Changes

**Before:**
- Only had "Get Recommendations" button
- No way to see or edit scheduling preferences
- Used synthetic demo data

**After:**
- Green "Scheduling Preferences" card (collapsible)
- Shows current preferences
- Can edit all optimization parameters
- Blue "Smart Scheduling" card below it
- Uses REAL data from your profile

## 🧪 Testing the Full Flow

### Test Case 1: High Urgency Patient
```
1. Login as patient
2. Set preferences:
   - Urgency: High
   - Max Distance: 10 km
   - Preferred Times: Morning
3. Save preferences
4. Get recommendations
Expected: Early morning timeslots, nearby doctors only
```

### Test Case 2: Flexible Patient
```
1. Set preferences:
   - Urgency: Low
   - Max Distance: 50 km
   - Preferred Times: Morning + Afternoon
2. Get recommendations
Expected: More options, wider range of times and doctors
```

### Test Case 3: Low Rehab Score (Critical)
```
1. Have low avg_quality_score in database (<3.0)
2. Get recommendations
Expected: Notification banner shows critical alert
          "Your exercise quality needs attention..."
          Urgency auto-elevated to High
```

## 📊 Database Tables Involved

```sql
-- Patient preferences
SELECT urgency, max_distance, specialty_needed, address
FROM patients WHERE user_id = ?;

-- Patient time preferences
SELECT timeslot_id, preference_score
FROM patient_time_preferences WHERE patient_id = ?;

-- Patient availability
SELECT timeslot_id, available
FROM patient_availability WHERE patient_id = ?;

-- Optimization results use all of the above!
```

## 🚀 Quick Demo

**To see the changes immediately:**

```bash
# If you haven't run migration yet:
python3 apply_migration.py
python3 update_existing_data.py

# Start the app:
python3 main.py

# In browser:
# 1. Go to http://localhost:5000/signup
# 2. Create a patient account (fill all new fields)
# 3. Login
# 4. Go to Appointments page
# 5. See the green "Scheduling Preferences" section!
```

## 🔑 Key Files Modified

- ✅ `templates/patient/appointments.html` - Added preferences UI
- ✅ `main.py` - Added `/api/patient/update-preferences` endpoint
- ✅ `main.py` - Updated `patient_appointments()` to pass preferences
- ✅ JavaScript - Added form handler and toggle function

## 💡 Next Steps

**Optional Enhancements:**
1. Add availability calendar (select specific days you're available)
2. Add preferred doctors list (not just one)
3. Show distance to each doctor in real km
4. Add geocoding to convert addresses to lat/long automatically
5. Show optimization score breakdown (why each doctor was recommended)

---

**Ready to test?** Login as a patient and click "Consultations"! 🎉
