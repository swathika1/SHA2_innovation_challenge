# Session Logging Implementation Guide

## Overview
This document describes the implementation of session data logging from the frontend to the database and dynamic dashboard metrics powered by that data.

## Features Implemented

### 1. Session Data Logging (Frontend → Database)

#### New API Endpoint: `/api/session/save`
- **Method**: POST
- **Authentication**: Required (login_required)
- **Purpose**: Saves completed exercise session data to the database

**Request Body:**
```json
{
  "workout_id": 1,
  "pain_before": 3,
  "pain_after": 2,
  "effort_level": 7,
  "quality_score": 75.5,
  "sets_completed": 3,
  "reps_completed": 30,
  "notes": "Felt good today"
}
```

**Response:**
```json
{
  "ok": true,
  "session_id": 42,
  "message": "Session saved successfully!"
}
```

#### Updated Session Flow
1. User starts a session → calls `/api/session/start` with `workout_id`
2. During session → quality scores are tracked in `allScores` array
3. User completes session → modal appears for pain/effort check-in
4. User submits data → calls `/api/session/save` with all metrics
5. Backend saves to `sessions` table and updates patient aggregate metrics
6. User redirected to dashboard with updated statistics

### 2. Dynamic Dashboard Metrics

#### Metrics Calculated from Database:

**Adherence Rate:**
- Formula: `(actual_sessions / expected_sessions) * 100`
- Expected sessions = number of active workouts × 30 days
- Actual sessions = sessions completed in last 30 days
- Updated after each session save

**Average Quality Score:**
- Average of `quality_score` from all sessions in last 30 days
- Range: 0-100
- Updated after each session save

**Average Pain Level:**
- Average of `pain_after` from all sessions in last 30 days
- Range: 0-10
- Updated after each session save

**Streak Days:**
- Consecutive days with at least one completed session
- Resets if no session yesterday or today
- Counts backward from most recent session

**Total Sessions:**
- Total count of all completed sessions (all time)

**Sessions This Week:**
- Count of sessions completed in last 7 days

### 3. Database Schema Updates

The `sessions` table already exists with the following structure:
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    workout_id INTEGER NOT NULL,
    pain_before INTEGER DEFAULT 0,
    pain_after INTEGER DEFAULT 0,
    effort_level INTEGER DEFAULT 5,
    quality_score REAL DEFAULT 0,
    sets_completed INTEGER DEFAULT 0,
    reps_completed INTEGER DEFAULT 0,
    notes TEXT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES users(id),
    FOREIGN KEY (workout_id) REFERENCES workouts(id)
);
```

### 4. Frontend Changes

#### session.html Template:
- Added `sessionStartTime` and `allScores[]` tracking
- Modified `startWebcam()` to call `/api/session/start` with `workout_id`
- Updated `updateFormStatus()` to track scores in `allScores` array
- Replaced `stopSession()` to show completion modal instead of redirect
- Added `showCompletionModal()` with pain/effort sliders
- Added `saveSessionData()` to POST data to `/api/session/save`

#### dashboard.html Template:
- Updated to show `formatted_date` for sessions
- Added total sessions count in header
- Shows rounded quality scores
- Displays reps completed alongside sets

### 5. Backend Helper Functions

**`update_patient_metrics(patient_id)`:**
- Calculates and updates aggregate metrics for a patient
- Called automatically after each session save
- Updates: adherence_rate, avg_quality_score, avg_pain_level, streak_days

**`calculate_streak(patient_id)`:**
- Determines consecutive days of activity
- Returns 0 if streak is broken
- Used by `update_patient_metrics()`

## Usage Flow

### For Patients:

1. **Start Session:**
   - Navigate to Dashboard → Click "Start Today's Session"
   - Click "Enable Camera" to start webcam
   - Perform exercises while AI analyzes form

2. **Complete Session:**
   - Click "Stop Session" button
   - Modal appears with check-in form:
     - Pain before exercise (0-10 slider)
     - Pain after exercise (0-10 slider)
     - Effort level (1-10 slider)
     - Optional notes (text area)
   - Click "Save & Continue" to save data
   - Redirected to dashboard with updated metrics

3. **View Progress:**
   - Dashboard shows real-time statistics:
     - Adherence Rate (%)
     - Day Streak (🔥)
     - Average Quality Score
     - Average Pain Level
   - Recent sessions list shows last 5 sessions
   - Each session displays: exercise name, date, quality, pain, sets/reps

## Testing the Implementation

### Manual Testing Steps:

1. **Test Session Creation:**
```bash
# Start the app
python3 main.py

# Login as a patient
# Navigate to /patient/session
# Click "Enable Camera"
# Verify session starts and scores are tracked
```

2. **Test Session Save:**
```bash
# Complete a session
# Click "Stop Session"
# Fill out the modal form
# Click "Save & Continue"
# Verify redirect to dashboard
# Check dashboard metrics are updated
```

3. **Test with cURL:**
```bash
# Save a session (requires active login session)
curl -X POST http://localhost:8000/api/session/save \
  -H "Content-Type: application/json" \
  -d '{
    "workout_id": 1,
    "pain_before": 3,
    "pain_after": 2,
    "effort_level": 7,
    "quality_score": 85,
    "sets_completed": 3,
    "reps_completed": 30,
    "notes": "Test session"
  }'
```

4. **Verify Database:**
```bash
sqlite3 rehab_coach.db
sqlite> SELECT * FROM sessions ORDER BY completed_at DESC LIMIT 5;
sqlite> SELECT * FROM patients WHERE user_id = YOUR_USER_ID;
```

## Error Handling

The implementation includes:
- ✅ Validation of workout_id and ownership
- ✅ Graceful handling of missing data
- ✅ Database transaction safety
- ✅ User-friendly error messages
- ✅ Console logging for debugging

## Future Enhancements

Potential improvements:
- Add session duration tracking
- Export session data as PDF/CSV
- Add graphs/charts for progress visualization
- Implement weekly/monthly reports
- Add notifications for streak milestones
- Compare sessions across different exercises
- Add session replay/review feature

## Files Modified

1. **main.py**
   - Added `/api/session/save` endpoint
   - Updated `patient_dashboard()` to calculate dynamic metrics
   - Added `update_patient_metrics()` helper function
   - Added `calculate_streak()` helper function
   - Modified `/api/session/start` to track workout_id

2. **templates/patient/session.html**
   - Added session state tracking variables
   - Modified webcam start to initialize session
   - Added completion modal with pain/effort form
   - Added `saveSessionData()` function
   - Updated score tracking

3. **templates/patient/dashboard.html**
   - Updated to display formatted dates
   - Added total sessions count
   - Improved session detail display

## Configuration

No additional configuration needed. The implementation uses:
- Existing database schema
- Existing Flask session management
- Existing authentication decorators
- Standard SQLite queries

## Support

For issues or questions:
1. Check browser console for JavaScript errors
2. Check Flask terminal for server errors
3. Verify database schema with `sqlite3 rehab_coach.db ".schema sessions"`
4. Ensure user is logged in and has active workouts
