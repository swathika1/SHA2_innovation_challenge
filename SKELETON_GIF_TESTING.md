# Quick Start: Testing Skeleton Visualization & Exercise GIFs

## Prerequisites

✅ All backend files are already integrated and production-ready

## Setup Steps

### 1. Verify GIF Directory Structure
```bash
# Create directory if needed
mkdir -p static/gifs/

# Check if GIFs exist (optional - system works without them)
ls -la static/gifs/
```

### 2. Start the Application
```bash
# From project root
python main.py
```

The application will start on `http://localhost:5000`

### 3. Launch Session

1. Log in as a Patient
2. Go to **Dashboard → Start New Session**
3. Select exercises (any will work for testing)
4. Click **Start Session**

### What You Should See

#### Upon Session Start ✅
- **Left Panel**: Live video feed from webcam
- **Middle Panel**: Black canvas with skeleton visualization
- **Right Panel**: Gray placeholder for exercise GIF
- **Console**: No JavaScript errors

#### During Exercise ✅
- **Skeleton Panel**: Real-time pose with 33 points and connections
- **Exercise GIF Panel**: Appropriate GIF loads based on detected exercise
- **Form Feedback**: LLM feedback includes pose information

#### Upon Session End ✅
- **Cleanup**: All polling stops, no console errors
- **Summary Screen**: Session statistics display normally

---

## Testing Checklist

### Skeleton Visualization
- [ ] Canvas renders without white space on load
- [ ] 33 landmarks visible in real-time
- [ ] Connection lines between joints visible
- [ ] Skeleton moves naturally as you move
- [ ] Confidence-based filtering (weak points fade/disappear)

### Exercise GIF Display
- [ ] GIF loads when exercise is first detected
- [ ] GIF changes when you switch exercises
- [ ] Placeholder displays if GIF file missing
- [ ] GIF displays on right panel consistently

### LLM Feedback
- [ ] Feedback mentions form/posture
- [ ] Contains pose information (alignment, lean, etc.)
- [ ] Generates feedback only on incorrect form
- [ ] Both pipelines work (general + KERAAL)

### Responsive Design
- [ ] Desktop: 3-column layout (video + skeleton + GIF)
- [ ] Tablet: 2-column layout collapses properly
- [ ] Mobile: 1-column layout stacks vertically

### Console Health
- [ ] No JavaScript errors
- [ ] Landmark polling logged every 200ms
- [ ] No memory leaks on session end

---

## Troubleshooting

### Skeleton Not Showing
```
Issue: Black canvas but no skeleton
Fix: Check /api/session/landmarks returns data
  → Flask log should show "Landmark storage" messages
```

### GIFs Not Loading
```
Issue: Gray placeholder instead of GIF
Possible Causes:
  1. GIF files missing from static/gifs/
     → Expected, system has fallback
  2. Wrong exercise name in mapping
     → Check normalizeExerciseName() in session.html
  3. CORS issue (rare)
     → Check browser console for CORS errors
```

### High CPU Usage
```
Issue: Skeleton rendering causes lag
Fix: Reduce polling frequency
  → Change 200 to 500 in startLandmarkPolling()
  → (line ~811 in session.html)
```

### Landmarks Endpoint Error
```
Issue: /api/session/landmarks returns 500
Fix: Verify session started with correct pipeline
  → Check Flask log for pipeline initialization
  → Ensure webcam permissions granted
```

---

## GIF Placeholder Text

If GIF files are missing, you'll see text like:
```
GIF: lifting_of_arms.gif
(not found - check static/gifs/)
```

This is **expected and acceptable**. The system works fully without GIFs, they're just visual enhancements.

---

## Performance Metrics

| Metric | Expected |
|--------|----------|
| Skeleton rendering | <5ms per frame |
| Landmark polling | 200ms interval |
| Memory per frame | <2MB |
| CPU usage | <15% (idle), <30% (active) |

---

## Common Exercises to Test

1. **Squat** (`squat.gif`)
   - Stand, squat down, stand back up
   - 2-3 reps should be detected

2. **Lifting of Arms** (`lifting_of_arms.gif`)
   - Raise arms from sides to shoulder height
   - Smooth motion, watch shoulder alignment

3. **Trunk Rotation** (`trunk_rotation.gif`)
   - Rotate torso side to side
   - Tests torso_lean metric

4. **Forward Flexion** (`forward_flexion.gif`)
   - Bend forward from waist
   - Tests shoulder and hip alignment

---

## Advanced Testing

### Check Landmarks in Console
```javascript
// In browser console, during active session:
fetch('/api/session/landmarks').then(r => r.json()).then(d => console.log(d.landmarks));
```

### Verify Pose Summary in LLM Context
```bash
# In Flask log, look for:
# "pose_summary: delta_motion=X.XXXX | shoulder_alignment=X.XX | ..."
```

### Monitor Polling
```javascript
// Check console for repeated messages:
// "[Landmarks] Fetched 33 points"
```

---

## File Locations

| Component | File |
|-----------|------|
| Session HTML | `templates/patient/session.html` |
| Web Pipeline | `Rehab_Scorer_Coach/src/web_pipeline.py` |
| KERAAL Pipeline | `Rehab_Scorer_Coach/src/keraal_pipeline.py` |
| API Backend | `main.py` (line 3427+) |
| GIFs | `static/gifs/*.gif` |

---

## Success Indicators

✅ All of these should be true:
- Skeleton canvas visible and updating
- GIF (or placeholder) visible in right panel
- No JavaScript errors in console
- Session completes normally
- Landmark polling stops on session end
- LLM feedback quality improved

---

## Next Steps

1. **Add Missing GIFs** (optional)
   - Source or create 8 exercise demonstration GIFs
   - Place in `static/gifs/` directory
   - System will automatically use them

2. **Customize Skeleton Colors** (optional)
   - Edit `drawSkeleton()` function in session.html
   - Add color coding (green=correct, red=incorrect)

3. **Add Pose Angles** (optional)
   - Enhance `drawSkeleton()` to show joint angles
   - Calculate using landmark positions

4. **Performance Tuning** (if needed)
   - Adjust polling interval based on hardware
   - Reduce canvas resolution on mobile

---

## Support

For issues, check:
1. Flask logs for backend errors
2. Browser console for JavaScript errors
3. Network tab for API responses
4. Check if all imports are installed

All core functionality is production-ready and fully integrated.

