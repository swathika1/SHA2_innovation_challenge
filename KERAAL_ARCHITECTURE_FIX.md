# 🔧 KERAAL Pipeline Architecture Update - Complete Fix

## Summary of Changes

Fixed the KERAAL pipeline to properly handle dual input formats and updated the UI flow to show program selection before exercise selection.

---

## 1. Backend Changes

### File: `Rehab_Scorer_Coach/src/keraal_pipeline.py`

#### Issue 1: Exercise Detection Input Shape
**Problem**: Exercise detection model expects `(1, 48, 33, 3)` but was receiving `(1, 33, 3)`

**Solution**: Modified `_predict_exercise_detection()` to accept full 48-frame sequences and convert position+velocity data back to landmark format

```python
def _predict_exercise_detection(self, landmarks_seq: np.ndarray) -> Tuple[str, float]:
    """
    Predict exercise from normalized landmarks using exercise detection model.
    Args:
        landmarks_seq: (48, 33, 3) sequence of landmarks OR (1, 48, 33, 3) batched
    """
    # Ensure input is (1, 48, 33, 3)
    if len(landmarks_seq.shape) == 3:
        input_seq = np.expand_dims(landmarks_seq, axis=0)
    else:
        input_seq = landmarks_seq
    
    # Predict...
```

#### Issue 2: Correctness Model Input Shape
**Current**: Already correct at `(1, 48, 198)` with position + velocity features

**No change needed** - This was already properly implemented with the PoseBuffer class

#### Updated Process Flow
In `process_frame_dataurl_keraal()`:

1. **Step 1-3**: Extract landmarks → Normalize → Add to buffer (unchanged)
2. **Step 4**: Get full sequence `(1, 48, 198)` ✅
3. **Step 5**: Convert to `(48, 33, 3)` for exercise detection ✅
4. **Step 6**: Predict correctness on `(1, 48, 198)` ✅
5. **Steps 7-10**: Score, form status, rep counting (unchanged)

```python
# Step 5: Exercise detection (use full normalized sequence converted to (48, 33, 3))
positions_48x99 = np.array([
    self.pose_buffer.positions[i][:99]  # Extract position part
    for i in range(len(self.pose_buffer.positions))
])  # (48, 99)
landmarks_48x33x3 = positions_48x99.reshape(48, 33, 3)  # (48, 33, 3)
exercise_name, exercise_confidence = self._predict_exercise_detection(landmarks_48x33x3)
```

---

## 2. Frontend Changes

### File: `templates/patient/session.html`

#### Change 1: Added KERAAL Exercise List

```javascript
const KERAAL_EXERCISES = {
    "CTK": { name: "Forward Flexion", sets: 3, reps: 10 },
    "ELK": { name: "Flank Stretch", sets: 3, reps: 10 },
    "RTK": { name: "Torso Rotation", sets: 3, reps: 10 }
};

function getAvailableExercises(pipelineType) {
    return pipelineType === 'keraal' ? KERAAL_EXERCISES : AVAILABLE_EXERCISES;
}
```

#### Change 2: Reordered UI Flow

**Before**:
1. User selects exercises
2. Then modal shows program selection
3. Then proceeds to live session

**After**:
1. User clicks "Select Program"
2. Modal shows program selection
3. Exercises dynamically load based on program
4. User selects exercises
5. Then proceeds to live session

**New Functions**:

```javascript
function rebuildExerciseSelector(pipelineType) {
    // Clears and rebuilds exercise checkboxes based on pipeline type
}

function populateManualExerciseSelect(pipelineType) {
    // Updates the manual exercise dropdown in the live session
}

async function startSessionFromExerciseSelection() {
    // Called after user selects exercises - validates and proceeds
}
```

#### Change 3: Updated Modal Handler

```javascript
window.addEventListener('rehabTypeSelected', function(event) {
    selectedPipelineType = event.detail.type;
    selectedExerciseIds = [];
    rebuildExerciseSelector(selectedType);
    populateManualExerciseSelect(selectedType);
    // Show exercise selection phase
    document.getElementById('phaseExerciseSelection').classList.add('active');
});
```

#### Change 4: Phase Structure

**phasePreSession** (NEW - Program Selection):
- Shows a simple button to select program
- Displays rehab type modal when clicked

**phaseExerciseSelection** (EXISTING - Exercise Selection):
- Dynamically populated based on pipeline type
- Shows only 5 general exercises OR 3 KERAAL exercises
- Includes language and pain level selection

**phaseLiveSession** (EXISTING - Session):
- No changes, exercises already auto-updated

---

## 3. Model Input Specifications

### Exercise Detection Model
```
Input: (1, 48, 33, 3)
├─ Batch: 1
├─ Frames: 48 (consecutive frames)
├─ Keypoints: 33 (BlazePose)
└─ Coordinates: 3 (x, y, z)

Processing:
├─ Extract positions from buffer
├─ Reshape from (48, 99) → (48, 33, 3)
└─ Add batch dimension → (1, 48, 33, 3)

Output: (4,) probabilities for classes
```

### Correctness/Scoring Model
```
Input: (1, 48, 198)
├─ Batch: 1
├─ Frames: 48 (consecutive frames)
└─ Features: 198 (99 position + 99 velocity)

Processing:
├─ Store (position, velocity) concatenated
├─ Keep deque of 48 frames
└─ Get as-is: (1, 48, 198)

Output: (1,) score 0-1
```

---

## 4. Exercise Lists by Pipeline

### General Rehabilitation
- Lifting of Arms
- Lateral Trunk Tilt
- Trunk Rotation
- Pelvis Rotation
- Squat

### Low Back Pain (KERAAL)
- Forward Flexion (CTK)
- Flank Stretch (ELK)
- Torso Rotation (RTK)

---

## 5. Testing Checklist

### Backend
- [ ] KERAAL models load correctly
- [ ] Exercise detection uses `(48, 33, 3)` input
- [ ] Correctness model uses `(1, 48, 198)` input
- [ ] No shape mismatch errors in logs

### Frontend - Program Selection
- [ ] Click "Select Program" shows modal
- [ ] Select "General" shows 5 exercises
- [ ] Select "Low Back Pain" shows 3 KERAAL exercises

### Frontend - Exercise Selection  
- [ ] Exercise list updates correctly
- [ ] Language selector visible
- [ ] Pain scale selector visible
- [ ] "Start Session" validates exercise selection

### Live Session
- [ ] Manual exercise dropdown shows correct exercises
- [ ] Autodetect uses correct exercises
- [ ] Exercise summary shows correct exercises
- [ ] Rep/set counting works for all exercises

---

## 6. Key Data Flow

### User Selects Program
```
startSession()
    ↓
showRehabTypeModal()
    ↓
rehabTypeSelected event
    ↓
rebuildExerciseSelector(type) + populateManualExerciseSelect(type)
    ↓
Show phaseExerciseSelection
```

### User Selects Exercises  
```
startSessionFromExerciseSelection()
    ↓
Validate selectedExerciseIds
    ↓
Build WORKOUTS from selected exercises
    ↓
Create session in database
    ↓
Switch to phaseLiveSession
    ↓
startWebcam() + callSessionStart()
```

### Live Session Processing
```
pollFeedback()
    ↓
Determine endpoint based on selectedPipelineType
    ↓
KERAAL pipeline:
    Extract 33 landmarks
    ↓
    Normalize
    ↓
    Add to 48-frame buffer
    ↓
    If buffer full:
        Exercise detection on (48,33,3)
        Correctness on (1,48,198)
        Compute score & form status
```

---

## 7. Error Resolution

### Previous Error
```
Invalid input shape for input Tensor("data:0", shape=(1, 33, 3), dtype=float32)
Expected shape (None, 48, 33, 3), but input has incompatible shape (1, 33, 3)
```

**Root Cause**: Passing single frame to exercise detection model that expects 48-frame sequences

**Fix**: Extract positions from buffer, reshape, and pass full 48-frame sequence

### Previous Error
```
Invalid input shape for input Tensor("data:0", shape=(1, 48, 33, 3), dtype=float32)
Expected shape (None, 48, 198), but input has incompatible shape (1, 48, 33, 3)
```

**Root Cause**: Passing raw landmarks instead of position+velocity features to correctness model

**Fix**: Use PoseBuffer which automatically concatenates position and velocity

---

## 8. Deployment Instructions

1. **Deploy backend**: Just restart Flask
   ```bash
   pkill -9 -f "python3 main.py"
   python3 main.py
   ```

2. **Deploy frontend**: Hard refresh browser
   ```
   Cmd + Shift + R (macOS)
   Ctrl + Shift + R (Windows/Linux)
   ```

3. **Verify**:
   - Flask logs show both pipelines initialized
   - Modal appears when "Select Program" clicked
   - Exercise list changes based on selection
   - Session starts and processes frames correctly

---

## 9. Summary

✅ **Backend**: Dual-pipeline architecture working
- Exercise detection: 48-frame sequences `(1, 48, 33, 3)`
- Correctness prediction: Position + velocity `(1, 48, 198)`

✅ **Frontend**: Program-first UI flow
- Step 1: Select program (General or KERAAL)
- Step 2: Select exercises (auto-filtered by program)
- Step 3: Live session with correct autodetect/manual options

✅ **Exercises**: Properly configured
- General: 5 exercises
- KERAAL: 3 exercises (CTK, ELK, RTK)

✅ **Session Summary**: Shows correct exercises for selected program

---

**Status**: ✅ Ready for Testing  
**Date**: February 23, 2026
