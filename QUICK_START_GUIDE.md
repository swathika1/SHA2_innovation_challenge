# Quick Start Guide - Session Logging & Dynamic Dashboard

## ✅ What's Been Implemented

### 1. Session Data Logging
- ✅ New API endpoint: `/api/session/save` to save session data from frontend
- ✅ Automatic calculation of metrics after each session
- ✅ Modal form for pain/effort check-in after completing exercise
- ✅ Quality scores tracked and averaged automatically

### 2. Dynamic Dashboard Metrics
- ✅ **Adherence Rate**: Calculated from sessions vs expected workouts
- ✅ **Streak Days**: Consecutive days with completed sessions
- ✅ **Avg Quality Score**: Average from last 30 days of sessions
- ✅ **Avg Pain Level**: Average pain after exercise from last 30 days
- ✅ **Total Sessions**: Lifetime count displayed in header
- ✅ **Recent Sessions**: Shows last 5 with quality, pain, sets, reps

## 🚀 How to Use

### For Testing:

1. **Start the Flask App** (already running):
   ```bash
   python3 main.py
   ```
   App runs on: https://localhost:8000

2. **Login as a Patient**:
   - Navigate to https://localhost:8000/login
   - Use patient credentials

3. **Complete a Session**:
   - Go to Dashboard → Click "Start Today's Session"
   - Click "Enable Camera" (webcam not required for testing)
   - Click "Stop Session" button
   - Fill out the modal form:
     * Pain before: 0-10
     * Pain after: 0-10
     * Effort level: 1-10
     * Notes (optional)
   - Click "Save & Continue"

4. **View Updated Dashboard**:
   - Check that metrics have updated:
     * Adherence Rate (%)
     * Day Streak 🔥
     * Average Quality Score
     * Average Pain Level
   - Check "Recent Sessions" shows your new session

### API Testing with cURL:

```bash
# First, get your session cookie by logging in through browser
# Then test the save endpoint:

curl -X POST https://localhost:8000/api/session/save \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "workout_id": 1,
    "pain_before": 3,
    "pain_after": 2,
    "effort_level": 7,
    "quality_score": 85,
    "sets_completed": 3,
    "reps_completed": 30,
    "notes": "Test session from API"
  }' \
  --insecure
```

## 🗄️ Database Queries for Verification

```bash
# Open database
sqlite3 rehab_coach.db

# View recent sessions
SELECT 
  s.id, s.patient_id, s.workout_id, 
  s.quality_score, s.pain_after, 
  s.sets_completed, s.reps_completed,
  datetime(s.completed_at, 'localtime') as completed
FROM sessions s
ORDER BY s.completed_at DESC
LIMIT 10;

# View patient metrics
SELECT 
  p.user_id, u.name,
  p.adherence_rate, p.streak_days,
  p.avg_quality_score, p.avg_pain_level
FROM patients p
JOIN users u ON p.user_id = u.id;

# Count sessions per patient
SELECT 
  p.user_id, u.name,
  COUNT(s.id) as total_sessions,
  AVG(s.quality_score) as avg_quality,
  AVG(s.pain_after) as avg_pain
FROM patients p
JOIN users u ON p.user_id = u.id
LEFT JOIN sessions s ON s.patient_id = p.user_id
GROUP BY p.user_id;

# Exit
.quit
```

## 📊 What Gets Updated Automatically

After each session save:

1. **Sessions Table**: New row inserted with all session data
2. **Patients Table**: Metrics recalculated:
   - `adherence_rate` = (actual_sessions / expected_sessions) × 100
   - `avg_quality_score` = average of last 30 days
   - `avg_pain_level` = average pain_after from last 30 days
   - `streak_days` = consecutive days with sessions

## 🐛 Troubleshooting

### Session not saving?
1. Check browser console (F12) for JavaScript errors
2. Check Flask terminal for server errors
3. Verify you're logged in as a patient
4. Verify `workoutId` is not null in session.html

### Metrics not updating?
1. Check database: `SELECT * FROM sessions ORDER BY completed_at DESC LIMIT 1;`
2. Check patient record: `SELECT * FROM patients WHERE user_id = YOUR_ID;`
3. Verify `update_patient_metrics()` is being called (check server logs)

### "Workout not found" error?
1. Make sure patient has active workouts assigned
2. Check: `SELECT * FROM workouts WHERE patient_id = YOUR_ID AND is_active = 1;`
3. If no workouts, ask a doctor to create one via clinician dashboard

## 📝 Code Flow

```
1. User starts session
   └─> JavaScript: startWebcam()
       └─> POST /api/session/start (stores workout_id in SESSION_STATE)

2. User performs exercises
   └─> JavaScript: updateFormStatus()
       └─> Tracks quality scores in allScores[] array

3. User clicks "Stop Session"
   └─> JavaScript: stopSession()
       └─> showCompletionModal() displays form

4. User fills form and clicks "Save & Continue"
   └─> JavaScript: saveSessionData()
       └─> POST /api/session/save with all data
           └─> Backend: api_session_save()
               ├─> Validates workout_id
               ├─> Inserts into sessions table
               ├─> Calls update_patient_metrics()
               │   ├─> Calculates adherence_rate
               │   ├─> Calculates avg_quality_score
               │   ├─> Calculates avg_pain_level
               │   └─> Calls calculate_streak()
               └─> Returns success response

5. User redirected to dashboard
   └─> Flask: patient_dashboard()
       ├─> Queries sessions for recent activity
       ├─> Queries patients for metrics
       └─> Renders with dynamic data
```

## 🎯 Key Files Modified

1. **main.py**
   - Line ~1071: `/api/session/save` endpoint
   - Line ~1120: `update_patient_metrics()` function
   - Line ~1180: `calculate_streak()` function
   - Line ~240: Updated `patient_dashboard()` route

2. **templates/patient/session.html**
   - Line ~224: Added session state variables
   - Line ~244: Modified `startWebcam()` to init session
   - Line ~288: Updated `updateFormStatus()` to track scores
   - Line ~375: Replaced `stopSession()` with modal flow
   - Line ~390: Added `showCompletionModal()`
   - Line ~450: Added `saveSessionData()`

3. **templates/patient/dashboard.html**
   - Line ~32: Added total_sessions in header
   - Line ~115: Updated recent sessions display

## 📈 Next Steps

To enhance further:
1. Add data visualization (charts/graphs)
2. Export session history to PDF/CSV
3. Add weekly/monthly progress reports
4. Implement goal setting and tracking
5. Add notifications for milestones
6. Create comparison views across exercises

## 🔒 Security Notes

- All endpoints require authentication (`@login_required`)
- Workout ownership is validated before saving
- SQL injection prevention via parameterized queries
- Session data validated before insert

## 📚 Additional Resources

- Full documentation: `SESSION_LOGGING_IMPLEMENTATION.md`
- Database schema: Check `main.py` line ~1220
- API documentation: See `/api/session/*` endpoints in main.py
