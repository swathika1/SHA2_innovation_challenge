# Dual Pipeline Rehab System Implementation Guide

## Overview

This implementation adds support for two distinct rehabilitation pipelines:

1. **General Rehabilitation** - Existing KIMORE-based pipeline with OpenPose
2. **Low Back Pain (KERAAL)** - NEW pipeline using BlazePose and Keras models

## Architecture

### Pipelines

#### General Rehabilitation Pipeline (Existing)
- **Feature Extraction**: OpenPose with 50D normalization
- **Exercise Detection**: RGB frame-based CNN classifier
- **Scoring**: 100-frame sequence predictions
- **Output**: Frame-level scores (0-50)
- **Model Files**:
  - `exercise_detection.keras` - Exercise classifier
  - `exercise_correctness_model.keras` - Scoring model
  - `scoring_scaler.pkl` - Feature scaler

#### Low Back Pain Pipeline (KERAAL) - NEW
- **Feature Extraction**: BlazePose 33 landmarks with normalization
- **Preprocessing**: 
  - Hip center normalization
  - Torso scaling
  - 48-frame rolling window buffer
- **Exercise Classes**:
  - `CTK`: Forward Flexion
  - `ELK`: Flank Stretch  
  - `RTK`: Torso Rotation
- **Scoring**: 0-1 correctness → multiply by 50 for raw score
- **Correctness Threshold**: >= 0.55 = CORRECT
- **Output**: Window-level predictions (48 frames)
- **Model Files**:
  - `keraal_exercise_detection.keras` - Exercise classifier
  - `keraal_model_v1.keras` - Correctness model

## File Structure

```
├── Rehab_Scorer_Coach/src/
│   ├── keraal_pipeline.py                    # NEW: KERAAL pipeline implementation
│   ├── web_pipeline.py                       # Existing general pipeline
│   └── models/
│       ├── keraal_exercise_detection.keras   # NEW model
│       └── keraal_model_v1.keras             # NEW model
├── templates/
│   ├── components/
│   │   └── rehab-type-modal.html            # NEW: Pipeline selector modal
│   └── patient/
│       └── session.html                      # Updated with modal integration
├── static/
│   ├── session.js                           # Legacy
│   └── session_manager.js                    # NEW: Unified session manager
└── main.py                                   # Updated with KERAAL endpoints
```

## New Files Created

### 1. `Rehab_Scorer_Coach/src/keraal_pipeline.py`

Complete KERAAL pipeline implementation with:
- `KeraalModelsLoader` - Singleton model manager
- `normalize_landmarks_keraal()` - Hip-center + torso scaling
- `PoseBuffer` - 48-frame rolling window
- `KeraalRehabPipeline` - Main pipeline class
  - `process_frame_dataurl_keraal()` - Frame processor
  - `_extract_mediapipe_landmarks_keraal()` - BlazePose extraction
  - `_predict_exercise_detection()` - Exercise classification
  - `_predict_correctness()` - Correctness scoring (0-1)
  - `_detect_and_count_reps()` - Rep counter

### 2. `templates/components/rehab-type-modal.html`

Beautiful modal UI for selecting rehabilitation type:
- Two option cards with icons and features
- Custom event dispatch system
- Responsive design
- Animation effects

### 3. `static/session_manager.js`

Unified session management class:
- `RehabSessionManager` class
  - Handles both 'general' and 'keraal' pipelines
  - Automatic endpoint routing
  - Rep counter updates
  - Notification system
- Global instance management
- Event-driven architecture

## Integration Changes

### main.py Updates

1. **Imports**:
```python
from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
```

2. **Pipeline Initialization**:
```python
# Initialize both pipelines
try:
    PIPELINE = WebRehabPipeline()
except Exception as e:
    PIPELINE = None

try:
    KERAAL_PIPELINE = KeraalRehabPipeline()
except Exception as e:
    KERAAL_PIPELINE = None
```

3. **New API Endpoints**:
- `POST /api/live_feedback_keraal` - KERAAL frame processing
- `POST /api/session/start/keraal` - Start KERAAL session
- `POST /api/session/stop/keraal` - Stop KERAAL session

### session.html Updates

1. **Global Variables**:
```javascript
let selectedPipelineType = 'general'; // or 'keraal'
```

2. **Updated Functions**:
- `startSession()` - Now shows modal instead of starting directly
- `continueSessionAfterPipelineSelection(pipelineType)` - Continues after selection
- `pollFeedback()` - Routes to correct API endpoint
- `callSessionStart()` - Routes to correct session start endpoint

3. **Modal Integration**:
```html
{% include 'components/rehab-type-modal.html' %}

<script>
window.addEventListener('rehabTypeSelected', function(event) {
    const selectedType = event.detail.type;
    continueSessionAfterPipelineSelection(selectedType);
});
</script>
```

## Usage Flow

### Patient Starting Session

1. Patient clicks "Start Session"
2. Selects exercises
3. Clicks "Start Session" button
4. **NEW**: Modal appears asking to select rehabilitation type
5. Chooses either:
   - **General Rehabilitation** → Uses existing pipeline
   - **Low Back Pain Program** → Uses KERAAL pipeline
6. Session begins with selected pipeline

### API Call Flow

#### General Rehabilitation
```
Frame → /api/live_feedback → WebRehabPipeline.process_frame_dataurl()
→ Response: {frame_score, form_status, exercise_name, llm_feedback, ...}
```

#### Low Back Pain (KERAAL)
```
Frame → /api/live_feedback_keraal → KeraalRehabPipeline.process_frame_dataurl_keraal()
→ Response: {frame_score, form_status, exercise_name, correctness, pipeline: 'keraal', ...}
```

## Response Format

### General Pipeline Response
```json
{
  "frame_score": 35.5,
  "form_status": "CORRECT",
  "exercise_name": "squat",
  "exercise_confidence": 0.95,
  "llm_feedback": ["Keep your back straight"],
  "rep_info": {
    "rep_now": 5,
    "rep_target": 10,
    "set_now": 1,
    "set_target": 3,
    "rep_incremented": true,
    "set_completed": false,
    "exercise_completed": false
  }
}
```

### KERAAL Pipeline Response
```json
{
  "frame_score": 25.0,
  "form_status": "CORRECT",
  "exercise_name": "Forward Flexion",
  "exercise_confidence": 0.87,
  "correctness": 0.5,
  "pipeline": "keraal",
  "llm_feedback": [],
  "rep_info": {
    "rep_now": 3,
    "rep_target": 10,
    "set_now": 1,
    "set_target": 3,
    "rep_incremented": true,
    "set_completed": false,
    "exercise_completed": false
  }
}
```

## Key Differences

| Feature | General | KERAAL |
|---------|---------|--------|
| Pose Detection | OpenPose 50D | BlazePose 33D |
| Feature Window | 100 frames | 48 frames |
| Score Range | 0-50 (direct) | 0-50 (correctness × 50) |
| Correctness Threshold | 35.0 (configurable) | 0.55 (fixed) |
| Exercise Classes | Multiple | CTK, ELK, RTK |
| LLM Feedback | Yes | No (for now) |
| Prediction Level | Frame-level | Window-level |

## Training & Models

### KERAAL Model Training Notes

The KERAAL models expect:

1. **Exercise Detection Model**:
   - Input: (1, 33, 3) normalized landmarks
   - Output: Classification logits for [CTK, ELK, RTK, idle, ...]

2. **Correctness Model**:
   - Input: (1, 48, 33, 3) sequence of normalized frames
   - Output: Single float 0-1 (correctness score)

### Feature Normalization

```python
# Hip center normalization (landmarks 23, 24)
hip_center = (landmarks[23] + landmarks[24]) / 2
normalized = landmarks - hip_center

# Torso scaling (landmark 11)
torso_length = np.linalg.norm(normalized[11])
normalized = normalized / torso_length
```

## Debugging

### Check Pipeline Initialization

```python
# In Flask app startup logs
print(PIPELINE)  # Should show WebRehabPipeline instance
print(KERAAL_PIPELINE)  # Should show KeraalRehabPipeline instance
```

### Monitor Frame Processing

Console logs show pipeline execution:
```
================ GENERAL FRAME PROCESSING ================
➡️ Step 1: OpenPose extraction
➡️ Step 2: 50D feature build
...

================ KERAAL FRAME PROCESSING ================
➡️ Step 1: MediaPipe extraction (BlazePose 33)
➡️ Step 2: Normalize landmarks
➡️ Step 3: Add to rolling buffer
...
```

### Frontend JavaScript Debug

```javascript
// In browser console
selectedPipelineType  // Check which pipeline is active
rehabSessionManager   // Access session manager instance
```

## Performance Considerations

- **KERAAL Buffer**: 48-frame buffer uses more memory than 100-frame window
- **BlazePose**: Lighter weight than OpenPose, faster processing
- **Correctness Scoring**: Window-level predictions may have slight latency

## Future Enhancements

1. Add LLM feedback to KERAAL pipeline
2. Implement pose visualization for KERAAL
3. Add more exercise classes
4. Support exercise-specific scoring thresholds
5. Add user preference for pipeline persistence

## Troubleshooting

### Models Not Loading

```
Error: FileNotFoundError: keraal_exercise_detection.keras
```

**Solution**: Ensure model files are in `Rehab_Scorer_Coach/models/` directory:
- `keraal_exercise_detection.keras`
- `keraal_model_v1.keras`

### Wrong Exercise Detected

- Ensure proper lighting and camera angle
- Check model training accuracy
- Verify landmark normalization is working

### Incorrect Scores

- Check correctness threshold (0.55 for KERAAL)
- Verify model output range (0-1)
- Review frame buffer filling (shows in logs)

## Testing

### Test KERAAL Pipeline Directly

```python
from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline

pipeline = KeraalRehabPipeline()
# Provide base64 encoded frame
result = pipeline.process_frame_dataurl_keraal(frame_b64)
print(result)
```

### Test Modal Display

1. Open browser DevTools
2. Navigate to session page
3. Click "Start Session"
4. Modal should appear with two options

## Support

For issues or questions:
- Check Flask logs for backend errors
- Check browser console for frontend errors
- Verify model files exist in correct location
- Ensure MediaPipe and TensorFlow are installed
