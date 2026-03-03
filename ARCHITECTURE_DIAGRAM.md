# 🎯 Integration Architecture Diagram

## End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REHABILITATION SESSION                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 1️⃣  VIDEO CAPTURE & PREPROCESSING                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Patient Video → Base64 Encode → /api/live_feedback (POST)                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 2️⃣  BACKEND PIPELINE PROCESSING (Both KIMORE & KERAAL)                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   📍 STEP 1: MediaPipe Pose Detection                                        │
│   ├─ Extract 33 landmarks (x, y, z coordinates)                             │
│   ├─ Confidence threshold: 0.5                                              │
│   └─ Output: landmarks array [33 points]                                    │
│                                                                              │
│   📍 STEP 2: Feature Engineering                                             │
│   ├─ KIMORE: Normalize pose → 50D feature vector                            │
│   ├─ KERAAL: Normalize + Rolling buffer (48 frames)                         │
│   └─ Output: feature vector for scoring                                     │
│                                                                              │
│   📍 STEP 3: Exercise Classification                                         │
│   ├─ CNN model predicts exercise type                                       │
│   ├─ KIMORE: 8 exercises (squat, arms, etc.)                                │
│   ├─ KERAAL: 3 exercises (CTK, ELK, RTK)                                    │
│   └─ Output: exercise_name + confidence                                     │
│                                                                              │
│   📍 STEP 4: Score Prediction                                                │
│   ├─ Model predicts form correctness (0-50)                                 │
│   ├─ Higher score = better form                                             │
│   └─ Output: frame_score, form_status (CORRECT/WRONG)                       │
│                                                                              │
│   📍 STEP 5: Rep Detection ⭐ NEW                                            │
│   ├─ MediaPipe rule-based detection                                         │
│   ├─ Input: landmarks + exercise_name                                       │
│   ├─ Method: Joint angle calculations                                       │
│   │  ├─ Squat: knee angle < 90° (down) → > 160° (up)                       │
│   │  ├─ Arm Lifting: shoulder-wrist distance high → low                     │
│   │  ├─ Lateral Tilt: side asymmetry > 15%                                  │
│   │  └─ ...7 more exercises                                                 │
│   └─ Output: rep_incremented (true/false)                                   │
│                                                                              │
│   📍 STEP 6: Gamification Badge Check ⭐ NEW                                 │
│   ├─ Backend calculates total reps in session                               │
│   ├─ Returns gamification state to frontend                                 │
│   └─ Output: rep_info with all metadata                                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 3️⃣  API RESPONSE SENT TO FRONTEND                                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ {                                                                            │
│   "frame_score": 34.5,                    ← Current form score              │
│   "form_status": "CORRECT",               ← Form quality                    │
│   "exercise_name": "squat",               ← Detected exercise               │
│   "exercise_confidence": 0.95,            ← Detection confidence            │
│   "rep_info": {                           ← REP COUNTER DATA ⭐             │
│     "rep_now": 5,                         ← Current rep                     │
│     "rep_target": 10,                     ← Target reps per set             │
│     "set_now": 1,                         ← Current set                     │
│     "set_target": 3,                      ← Target sets                     │
│     "rep_incremented": true,              ← NEW REP COUNTED!                │
│     "set_completed": false,               ← Set finished?                   │
│     "exercise_completed": false           ← All sets done?                  │
│   },                                                                         │
│   "landmarks": [                          ← SKELETON DATA ⭐                │
│     [0.5, 0.3, 0.0],   ← landmark 1 (x, y, z)                              │
│     [0.51, 0.31, -0.01],← landmark 2                                       │
│     ...                                                                      │
│     [0.55, 0.35, 0.02]  ← landmark 33                                      │
│   ],                                                                         │
│   "llm_feedback": ["Keep your back straight!", ...]  ← AI feedback         │
│ }                                                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 4️⃣  FRONTEND PROCESSING                                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   A) UPDATE REP COUNTER                                                      │
│   ├─ Display: "5 / 10" (current / target)                                   │
│   ├─ Display: "Set 1 of 3"                                                  │
│   └─ Show success message if rep_incremented = true                         │
│                                                                              │
│   B) UPDATE GAMIFICATION ⭐                                                 │
│   ├─ Calculate total reps: (currentSet - 1) * 10 + currentRep               │
│   ├─ Check badge unlock conditions:                                         │
│   │  ├─ totalReps >= 1? Unlock 🎯 First Step                               │
│   │  ├─ totalReps >= 10? Unlock 💪 One Set                                 │
│   │  ├─ totalReps >= 20? Unlock 🔥 Pair Power                              │
│   │  ├─ totalReps >= 30? Unlock 🏆 Champion                                │
│   │  └─ ...more badges                                                     │
│   ├─ Update streak counter (currentStreak = totalReps)                     │
│   └─ Show notification popup when badge unlocked                            │
│                                                                              │
│   C) SKELETON VISUALIZATION (via video_call.html) ⭐                        │
│   ├─ Call /api/session/landmarks every 200ms                               │
│   ├─ Get latest landmarks                                                   │
│   ├─ Draw 33 pose points on canvas                                          │
│   ├─ Connect with skeleton lines                                            │
│   └─ Real-time pose feedback                                                │
│                                                                              │
│   D) DISPLAY FEEDBACK                                                        │
│   ├─ Show form_status: "CORRECT" or "WRONG"                                │
│   ├─ Play audio feedback if incorrect                                       │
│   └─ Update progress bar                                                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ 5️⃣  LANDMARK POLLING (Continuous, Independent)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Every 200ms:                                                               │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │ GET /api/session/landmarks                                      │       │
│   │ ↓                                                               │       │
│   │ LATEST_LANDMARKS['kimore'] or ['keraal']                       │       │
│   │ ↓                                                               │       │
│   │ Return: {                                                       │       │
│   │   "landmarks": [[x1,y1,z1], [x2,y2,z2], ...],  ← 33 points    │       │
│   │   "exercise_name": "squat",                                    │       │
│   │   "timestamp": 1704067200.123                                  │       │
│   │ }                                                               │       │
│   │ ↓                                                               │       │
│   │ skeleton_visualizer.drawPose(landmarks)                        │       │
│   │ ↓                                                               │       │
│   │ Real-time skeleton on screen 🦴                                │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│   Independent polling cycle:                                                │
│   - Doesn't block main feedback loop                                        │
│   - Asynchronous (no await)                                                 │
│   - Continuous throughout session                                           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Architecture Summary

### Component Relationship Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       FRONTEND (Session.html)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────────┐  ┌──────────────────────────────────────┐ │
│  │  Rep Counter Display   │  │  Gamification UI (NEW)               │ │
│  │  "5 / 10 reps"         │  │  - Streak: 5 🔥                      │ │
│  │  "Set 1 of 3"          │  │  - Badge Grid (9 badges)             │ │
│  │                        │  │  - Unlock animations                 │ │
│  └────────────────────────┘  └──────────────────────────────────────┘ │
│           ↑                                   ↑                        │
│           │                                   │                        │
│  ┌────────┴─────────────────────────┬────────┴─────────────────────┐  │
│  │                                  │                              │  │
│  │  pollFeedback() - Every 200ms   │  Landmark Polling (NEW)      │  │
│  │  POST /api/live_feedback        │  GET /api/session/landmarks │  │
│  │  ↓                              │  ↓                          │  │
│  │  Response with rep_info ✅      │  Returns 33 landmarks ✅    │  │
│  │  + landmarks ✅                 │  + exercise_name           │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                    │                                  │
└────────────────────────────────────┼──────────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ↓                                       ↓
        ┌─────────────────────────┐         ┌─────────────────────────┐
        │  WebRehabPipeline       │         │ KeraalRehabPipeline     │
        │  (KIMORE exercises)     │         │ (Low back pain)         │
        │                         │         │                         │
        │ ┌─────────────────────┐ │         │ ┌─────────────────────┐ │
        │ │ MediaPipe Detection │ │         │ │ MediaPipe Detection │ │
        │ │ - 33 landmarks      │ │         │ │ - 33 landmarks      │ │
        │ └─────────────────────┘ │         │ └─────────────────────┘ │
        │           ↓              │         │           ↓              │
        │ ┌─────────────────────┐ │         │ ┌─────────────────────┐ │
        │ │ 50D Feature Vector  │ │         │ │ Pose Buffer + 48f   │ │
        │ │ + Exercise Model    │ │         │ │ + Feature Extraction│ │
        │ └─────────────────────┘ │         │ └─────────────────────┘ │
        │           ↓              │         │           ↓              │
        │ ┌─────────────────────┐ │         │ ┌─────────────────────┐ │
        │ │ Score Model         │ │         │ │ Exercise Model      │ │
        │ │ (0-50 form score)   │ │         │ │ + Correctness Model │ │
        │ └─────────────────────┘ │         │ └─────────────────────┘ │
        │           ↓              │         │           ↓              │
        │ ┌─────────────────────┐ │         │ ┌─────────────────────┐ │
        │ │ RepCounterMediaPipe │ │         │ │ RepCounterMediaPipe │ │
        │ │ (NEW) ✅             │ │         │ │ (NEW) ✅             │ │
        │ │ Uses joint angles   │ │         │ │ Uses joint angles   │ │
        │ │ - 8 exercises       │ │         │ │ - 3 exercises       │ │
        │ └─────────────────────┘ │         │ └─────────────────────┘ │
        │           ↓              │         │           ↓              │
        │ ┌─────────────────────┐ │         │ ┌─────────────────────┐ │
        │ │ Response Builder    │ │         │ │ Response Builder    │ │
        │ │ Returns:            │ │         │ │ Returns:            │ │
        │ │ - rep_info ✅       │ │         │ │ - rep_info ✅       │ │
        │ │ - landmarks ✅      │ │         │ │ - landmarks ✅      │ │
        │ │ - form_status       │ │         │ │ - form_status       │ │
        │ │ - llm_feedback      │ │         │ │ - llm_feedback      │ │
        │ └─────────────────────┘ │         │ └─────────────────────┘ │
        └─────────────────────────┘         └─────────────────────────┘
                     ↑                                    ↑
                     │                                    │
                     └────────────────┬───────────────────┘
                                      │
                          ┌───────────┴────────────┐
                          │                        │
                   ┌──────────────────┐   ┌─────────────────┐
                   │ Store Landmarks  │   │ Store Landmarks │
                   │ in:              │   │ in:             │
                   │ LATEST_LANDMARKS │   │ LATEST_LANDMARKS│
                   │ ['kimore']       │   │ ['keraal']      │
                   └──────────────────┘   └─────────────────┘
                          ↑                        ↑
                          │                        │
                          └───────────┬────────────┘
                                      │
                              /api/session/landmarks
                              (GET endpoint)
                                      │
                                      ↓
                              Frontend receives
                              latest landmarks
                              for skeleton drawing
```

## Key Integration Points

### 1. Rep Counter Integration

**Before:**
```
Frame → MediaPipe → Features → Score → Frame-count rep
```

**After:**
```
Frame → MediaPipe landmarks ──┐
                              ├→ Features → Score
                              ├→ RepCounterMediaPipe (rule-based)
                              │   - Joint angles
                              │   - Exercise-specific detection
                              │   - Returns: rep_detected (bool)
```

### 2. Landmarks Exposure

**Before:**
```
Landmarks extracted but discarded
Frame processing → Score → Response (no landmarks)
```

**After:**
```
Landmarks extracted → Stored in response → Returned to frontend
                   ↓
              Also stored in LATEST_LANDMARKS dict
                   ↓
              Available via /api/session/landmarks endpoint
                   ↓
              Frontend polls every 200ms for skeleton visualization
```

### 3. Gamification Integration

**Before:**
```
Session → Rep counter → Rep count displayed
```

**After:**
```
Session → initializeGamification()
            ↓
         Rep counter incremented
            ↓
         updateGamificationOnRepCount()
            ↓
         Check badge conditions
            ↓
         Unlock badges + show notifications
```

## Timeline

```
T=0s     Session starts
         ├─ initializeGamification() renders badge grid
         └─ Main loop begins

T=5s     User completes first rep
         ├─ rep_incremented = true
         ├─ Rep counter updates to "1 / 10"
         ├─ updateGamificationOnRepCount(1) called
         ├─ Badge: 🎯 First Step unlocks
         └─ Notification popup shows

T=15s    User completes 10th rep (first set done)
         ├─ Rep counter updates to "0 / 10" (new set)
         ├─ set_completed = true
         ├─ updateGamificationOnRepCount(10) called
         ├─ Badge: 💪 One Set unlocks
         ├─ Alert: "Set 1 completed!"
         └─ Current set increments to "Set 2 of 3"

T=25s    User completes 20 reps total
         ├─ updateGamificationOnRepCount(20) called
         ├─ Badge: 🔥 Pair Power unlocks
         └─ Notification popup shows

T=35s    User completes all 30 reps (3 sets × 10 reps)
         ├─ exercise_completed = true
         ├─ updateGamificationOnRepCount(30) called
         ├─ Badge: 🏆 Champion unlocks
         ├─ Alert: "Exercise complete!"
         ├─ Gamification final state saved
         └─ Session completes

Throughout:
  ├─ Every 200ms: /api/session/landmarks called
  ├─ Landmarks used for skeleton visualization
  ├─ Rep detection happens via MediaPipe angles
  └─ Form feedback continues from scoring model
```

---

**Architecture Complete** ✅
All components integrated and operational!
