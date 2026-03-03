# 🧪 KERAAL Model Input Shape Fix - Testing Guide

## Quick Start

### 1. Kill old Flask instances
```bash
pkill -9 -f "python3 main.py"
sleep 2
```

### 2. Start Flask
```bash
cd /Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge
python3 main.py
```

### 3. Expected Startup Output

```
✅ Loaded exercise detection model: .../keraal_exercise_detection.keras
✅ Loaded correctness model: .../keraal_model_v1.keras
✅ KERAAL Models Ready
✅ KeraalRehabPipeline Ready
[INIT] KeraalRehabPipeline (Low Back Pain) initialized successfully
...
* Running on http://127.0.0.1:5050
```

### 4. Open Browser
- Go to: `http://127.0.0.1:5050/patient/session`
- Login if needed
- Click "Start Session"
- Select "Low Back Pain" from modal
- Allow camera access

### 5. Monitor Terminal Output

#### Warmup Phase (First 48 frames)
```
➡️ Step 1: MediaPipe extraction (BlazePose 33)
➡️ Step 2: Normalize landmarks (hip center + torso scaling)
➡️ Step 3: Add to rolling buffer
   Buffer: 1/48 frames
   ...Buffer warming up...
   Buffer: 47/48 frames
```

#### Active Phase (After 48 frames)
```
➡️ Step 1: MediaPipe extraction (BlazePose 33)
➡️ Step 2: Normalize landmarks (hip center + torso scaling)
➡️ Step 3: Add to rolling buffer
   Buffer: 48/48 frames
➡️ Step 4: Window-level predictions (buffer full)
➡️ Step 5: Exercise detection
   Exercise: Forward Flexion (conf=0.952)
➡️ Step 6: Correctness prediction
   ✅ Predicting correctness from shape: (1, 48, 198)
   Correctness: 0.782
   Raw score: 39.10/50
   Form status: CORRECT
➡️ Step 7: Window-level rep detection
➡️ Returning response
127.0.0.1 - - [23/Feb/2026 21:04:10] "POST /api/live_feedback_keraal HTTP/1.1" 200 -
```

---

## Success Criteria ✅

### Terminal Logs
- ✅ No `Invalid input shape` errors
- ✅ Shape shows `(1, 48, 198)` (not `1, 48, 33, 3`)
- ✅ Correctness values are between 0 and 1
- ✅ Raw scores are between 0 and 50
- ✅ All HTTP responses are `200 OK` (not `503`)

### Browser Display
- ✅ Modal appears with two options
- ✅ Can select "Low Back Pain"
- ✅ Video starts from camera
- ✅ After ~2 seconds, feedback appears
- ✅ Form status shows CORRECT or INCORRECT
- ✅ Rep counter updates
- ✅ No errors in DevTools console

---

## Troubleshooting

### Issue: Still seeing "Invalid input shape (1, 48, 33, 3)"

**Solution**: 
1. Verify file was updated: 
   ```bash
   grep -n "FRAME_FEATURES = 198" Rehab_Scorer_Coach/src/keraal_pipeline.py
   ```
2. Kill Flask and restart
3. Check for old .pyc files:
   ```bash
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null
   ```

### Issue: "Connection refused" or "Network error"

**Solution**:
```bash
# Check Flask is running
lsof -i :5050

# If not, start it:
python3 main.py
```

### Issue: "No pose detected" repeatedly

**Solution**:
1. Check camera is working
2. Try different lighting
3. Ensure full body is visible
4. Try moving closer to camera

---

## Key Metrics to Monitor

| Metric | Expected Range | Notes |
|--------|-----------------|-------|
| Buffer size | 1-48 | Should increase then stay at 48 |
| Correctness | 0.000 - 1.000 | 0.55+ = CORRECT |
| Raw score | 0.00 - 50.00 | correctness × 50 |
| Exercise confidence | 0.0 - 1.0 | Higher is better |
| HTTP status | 200 OK | Every request |
| Inference time | 30-50ms | Per prediction |

---

## Full Workflow Example

```
1. Flask starts
   ✅ KeraalRehabPipeline initialized
   ✅ Models loaded

2. User selects "Low Back Pain"
   ✅ Session created
   ✅ /api/session/start/keraal called (200 OK)

3. Camera frames being sent
   ✅ /api/live_feedback_keraal called repeatedly

4. First 48 frames (warmup)
   Response: {"form_status": "WARMUP", "frame_score": 0.0}

5. Frame 49+ (predictions active)
   Response: {
     "form_status": "CORRECT",
     "frame_score": 39.10,
     "exercise_name": "Forward Flexion",
     "exercise_confidence": 0.952,
     "correctness": 0.782,
     "rep_info": {
       "rep_now": 2,
       "rep_target": 10,
       "set_now": 1,
       "set_target": 3,
       "rep_incremented": false
     }
   }

6. User finishes exercise
   ✅ /api/session/stop/keraal called (200 OK)
```

---

## Important Notes

### Shape Verification (from code)
```python
FRAME_FEATURES = 198  # 99 position + 99 velocity
sequence.shape = (1, 48, 198)  # Batch, frames, features

# Breakdown:
# 33 keypoints × 3 coordinates = 99 position features
# 99 position features (velocity) = 99 velocity features
# Total = 99 + 99 = 198 features per frame
```

### Velocity Computation
```python
# Each frame includes position + velocity
position[t] = normalized_landmarks[t]  # (99,)
velocity[t] = position[t] - position[t-1]  # (99,)
frame_features[t] = [position[t], velocity[t]]  # (198,)
```

---

## Commands for Testing

### Test KERAAL endpoint directly:
```bash
curl -X POST http://127.0.0.1:5050/api/session/start/keraal \
  -H "Content-Type: application/json" \
  -d '{"language": "English"}' \
  -v
```

Expected response (200 OK):
```json
{"status": "success", "message": "Session started"}
```

### Check Flask process:
```bash
ps aux | grep "python3 main.py" | grep -v grep
```

### Monitor Flask logs in real-time:
```bash
# In separate terminal while Flask is running
tail -f /tmp/flask.log 2>/dev/null || echo "No log file"
```

### Clear all Python cache:
```bash
find . -name "*.pyc" -delete && \
find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null && \
echo "Cache cleared"
```

---

## Final Verification Checklist

Before considering the fix complete:

- [ ] Flask starts without errors
- [ ] KERAAL models load successfully  
- [ ] Can select "Low Back Pain" from modal
- [ ] Camera access works
- [ ] First 48 frames show "WARMUP" status
- [ ] Frame 49+ shows actual predictions
- [ ] Correctness values are realistic (0-1)
- [ ] Raw scores are correct (0-50)
- [ ] Form status changes between CORRECT/INCORRECT
- [ ] Rep counter increments
- [ ] No shape errors in Flask logs
- [ ] All API responses are 200 OK
- [ ] No errors in browser console

✅ If all checked, you're good to go!

---

**Last Updated**: February 23, 2026  
**Status**: Ready to Test ✅
