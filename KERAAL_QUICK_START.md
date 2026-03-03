# KERAAL Low Back Pain Pipeline - Quick Start Guide

## 🚀 Setup Checklist

### 1. Model Files
Verify the following files exist in `Rehab_Scorer_Coach/models/`:
- ✅ `keraal_exercise_detection.keras` - Exercise classifier
- ✅ `keraal_model_v1.keras` - Correctness/scoring model

### 2. Required Dependencies

The following are already in your environment:
- TensorFlow/Keras
- MediaPipe (for BlazePose)
- NumPy
- OpenCV (cv2)

### 3. Python Files
New files added:
- ✅ `Rehab_Scorer_Coach/src/keraal_pipeline.py` - Core pipeline

### 4. Frontend Files
New files added:
- ✅ `templates/components/rehab-type-modal.html` - Selection modal
- ✅ `static/session_manager.js` - Unified session manager

### 5. Template Updates
Modified files:
- ✅ `templates/patient/session.html` - Integrated modal and pipeline selection
- ✅ `main.py` - Added KERAAL endpoints and pipeline initialization

## 🎯 How to Test

### Test 1: Verify Backend Initialization

**Run Flask app:**
```bash
python main.py
```

**Check startup logs:**
```
[INIT] WebRehabPipeline (General Rehab) initialized successfully
[INIT] KeraalRehabPipeline (Low Back Pain) initialized successfully
```

If you see these messages, both pipelines are ready! ✅

### Test 2: Test Modal Display

1. Open browser and navigate to patient session page
2. Log in as patient
3. Select some exercises
4. Click "Start Session" button
5. **Expected**: A beautiful modal should appear with:
   - "General Rehabilitation" option on left
   - "Low Back Pain Program" option on right
   - Animated icons and feature lists

### Test 3: Test KERAAL Pipeline

1. In the modal, click "Start Low Back Pain Program"
2. Allow camera access
3. Position yourself in frame
4. **Expected Behavior**:
   - You'll see "Skeleton Tracking: ON" in the video
   - Status badge will show "ANALYZING..."
   - After ~1.6 seconds (48 frames at ~30fps), predictions start
   - Form status will show "CORRECT" or "INCORRECT"
   - Rep counter will update when correct form is held for ~20 frames

### Test 4: Check API Responses

**Open browser DevTools → Network tab:**

1. Select "Low Back Pain Program"
2. Watch network requests to:
   - `POST /api/session/start/keraal` - Session initialization
   - `POST /api/live_feedback_keraal` - Frame processing

**Example response from `/api/live_feedback_keraal`:**
```json
{
  "frame_score": 25.0,
  "form_status": "CORRECT",
  "exercise_name": "Forward Flexion",
  "exercise_confidence": 0.87,
  "correctness": 0.5,
  "pipeline": "keraal",
  "rep_info": {
    "rep_now": 3,
    "rep_target": 10,
    "set_now": 1,
    "set_target": 3,
    "rep_incremented": true
  }
}
```

## 📊 Understanding the Scores

### Score Display
- **Frame Score**: 0-50 (correctness × 50)
- **Correctness**: 0-1 (raw model output)
- **Formula**: `raw_score = correctness_score * 50`

### Form Status
- **CORRECT**: `correctness >= 0.55` (threshold)
- **INCORRECT**: `correctness < 0.55`

### Example
- Correctness: 0.6 → Score: 30 → Status: ✓ CORRECT
- Correctness: 0.4 → Score: 20 → Status: ✗ INCORRECT

## 🏋️ Exercise Classes

When using Low Back Pain program, you'll see:

| Code | Display Name | Description |
|------|-------------|-------------|
| CTK | Forward Flexion | Forward bending motion |
| ELK | Flank Stretch | Side body stretch |
| RTK | Torso Rotation | Twisting motion |

## 🔍 Real-Time Debugging

### Browser Console (F12)
```javascript
// Check selected pipeline
selectedPipelineType  // Should be "keraal"

// Check session manager
rehabSessionManager

// Check session state
rehabSessionManager.pipelineType
rehabSessionManager.isRunning
```

### Flask Console
Watch for debug logs:
```
================ KERAAL FRAME PROCESSING ================
➡️ Step 1: MediaPipe extraction (BlazePose 33)
   Frame: (480, 640)
➡️ Step 2: Normalize landmarks (hip center + torso scaling)
➡️ Step 3: Add to rolling buffer
   Buffer: 45/48 frames
```

## ⚡ Performance Tips

### For Better Results
1. **Lighting**: Ensure good lighting on your body
2. **Distance**: Stay 1-1.5 meters from camera
3. **Posture**: Clear, visible body movements
4. **Camera**: 720p or higher resolution
5. **Position**: Center yourself in frame

### Optimization
- KERAAL uses 48-frame window (vs 100 for general)
- Predictions every ~1.6 seconds (at 30fps)
- BlazePose is faster than OpenPose
- Less memory intensive than general pipeline

## 🐛 Common Issues & Solutions

### Issue: Modal doesn't appear
**Solution**: 
- Check browser console for JavaScript errors
- Verify modal HTML is being rendered: `Ctrl+Shift+I` → Elements tab
- Search for "rehab-type-modal" in page source

### Issue: KERAAL pipeline not initializing
**Solution**:
- Check Flask startup logs for model loading errors
- Verify model files exist: `ls Rehab_Scorer_Coach/models/keraal_*.keras`
- Check if TensorFlow can load models

### Issue: No pose detected
**Solution**:
- Better lighting (avoid shadows)
- Move closer to camera
- Make sure full body is visible
- Check camera permissions

### Issue: Scores always 0
**Solution**:
- Wait for buffer to fill (first ~1.6 seconds)
- Check if pose is being detected
- Verify model output (should be 0-1)
- Check correctness threshold setting

## 📈 Next Steps

### For Production
1. ✅ Test both pipelines side-by-side
2. ✅ Verify rep counting accuracy
3. ✅ Test form status threshold (currently 0.55)
4. ✅ Collect user feedback
5. ⏳ Fine-tune model thresholds based on real usage

### Enhancement Ideas
- [ ] Add LLM coaching feedback to KERAAL
- [ ] Implement pose visualization overlay
- [ ] Add exercise difficulty levels
- [ ] Store KERAAL-specific metrics
- [ ] Create KERAAL-specific analytics dashboard

## 📞 Support

**Quick Reference:**
- KERAAL API endpoint: `/api/live_feedback_keraal`
- KERAAL session start: `/api/session/start/keraal`
- KERAAL session stop: `/api/session/stop/keraal`
- Modal event: `rehabTypeSelected`
- Pipeline type variable: `selectedPipelineType`

**Debug Command (Python):**
```python
from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
p = KeraalRehabPipeline()
print(f"Pipeline: {p}")
print(f"Models: {p.models}")
```

---

**Status**: ✅ Ready for Testing

All files created, integrated, and ready to test!
