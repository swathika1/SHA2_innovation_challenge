# 🚀 Quick Start: Getting Gamified UI Features Live in 30 Minutes

This guide gets you from code to working features with minimal setup.

## ⏱️ Timeline: 30 Minutes

- **5 min**: Copy files
- **5 min**: Update HTML template
- **5 min**: Update session.js
- **10 min**: Test features
- **5 min**: Troubleshoot any issues

## 📋 Prerequisite Checklist

Before starting, ensure you have:
- [ ] Both pipeline files (web_pipeline.py, keraal_pipeline.py)
- [ ] Flask app running on localhost:5000
- [ ] Browser with modern JavaScript (Chrome, Safari, Firefox)
- [ ] Camera/video stream access
- [ ] Main branch code pulled

---

## Step 1: Copy Files (2 minutes)

### 1.1 Copy Rep Counter Backend

```bash
# Copy rep counter to both pipelines
cp Rehab_Scorer_Coach/src/rep_counter_mediapipe.py Rehab_Scorer_Coach/src/
```

**File**: `Rehab_Scorer_Coach/src/rep_counter_mediapipe.py` (Already in workspace)

### 1.2 Copy Frontend Files

```bash
# Copy JavaScript files
cp static/skeleton_visualization.js static/
cp static/gamification.js static/

# Copy CSS file
cp static/gamified_ui.css static/
```

**Verify files exist**:
```bash
ls -la static/skeleton_visualization.js
ls -la static/skeleton_visualization.js
ls -la static/gamified_ui.css
```

---

## Step 2: Update HTML Template (5 minutes)

### 2.1 Edit: `templates/patient/session.html`

Replace the content with the integration guide's HTML template. Key changes:

```html
<!-- Add new CSS at top -->
<link rel="stylesheet" href="{{ url_for('static', filename='gamified_ui.css') }}">

<!-- Add 3-column layout -->
<div class="session-grid">
    <!-- Skeleton Section -->
    <div class="skeleton-section">
        <canvas id="skeletonCanvas" class="skeleton-canvas" width="300" height="400"></canvas>
    </div>
    
    <!-- GIF Section -->
    <div class="gif-section">
        <img id="exerciseGif" class="exercise-gif" src="">
    </div>
    
    <!-- Gamification Section -->
    <div class="stats-section">
        <div id="gamification-container"></div>
    </div>
</div>

<!-- Add scripts at bottom -->
<script src="{{ url_for('static', filename='skeleton_visualization.js') }}"></script>
<script src="{{ url_for('static', filename='gamification.js') }}"></script>
<script src="{{ url_for('static', filename='session.js') }}"></script>
```

**Or use the full template from**: `PHASE_2_3_INTEGRATION_GUIDE.md`

---

## Step 3: Update Session JavaScript (5 minutes)

### 3.1 Create/Update: `static/session.js`

Core initialization code:

```javascript
// ===== INITIALIZATION =====
let gamificationEngine;
let gamificationUI;
let skeletonVisualizer;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Gamification
    gamificationEngine = new GamificationEngine();
    gamificationUI = new GamificationUI(gamificationEngine, 'gamification-container');

    // Skeleton visualization
    skeletonVisualizer = new SkeletonVisualizer('skeletonCanvas');

    // Start polling
    startSessionPolling();
});

// ===== POLLING =====
function startSessionPolling() {
    setInterval(async () => {
        try {
            const response = await fetch('/api/session/landmarks');
            const data = await response.json();

            if (data.landmarks) {
                // Draw skeleton
                skeletonVisualizer.draw(data.landmarks);

                // Update form status
                updateFormStatus(data.form_status, data.feedback);

                // Record rep if detected
                if (data.rep_detected) {
                    const result = gamificationEngine.recordRep(
                        data.form_status === 'CORRECT'
                    );
                    
                    // Update UI
                    gamificationUI.updateRepCounter(
                        result.repCount,
                        gamificationEngine.getMotivationalMessage()
                    );
                }
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 200); // 5 FPS
}

// ===== FORM STATUS =====
function updateFormStatus(status, feedback) {
    const indicator = document.getElementById('formStatusIndicator');
    if (!indicator) return;

    if (status === 'CORRECT' || status === 'CORRECT_FORM') {
        indicator.className = 'form-status-indicator correct';
        indicator.innerHTML = `
            <span class="form-status-icon">✓</span>
            <span>${feedback || 'Good Form!'}</span>
        `;
    } else {
        indicator.className = 'form-status-indicator incorrect';
        indicator.innerHTML = `
            <span class="form-status-icon">✗</span>
            <span>${feedback || 'Adjust form'}</span>
        `;
    }
    
    indicator.style.display = 'flex';
}
```

---

## Step 4: Update Backend (5 minutes)

### 4.1 Update: `Rehab_Scorer_Coach/src/web_pipeline.py`

Add rep counter integration:

```python
from rep_counter_mediapipe import RepCounterMediaPipe
import numpy as np

class WebRehabPipeline:
    def __init__(self):
        # ... existing code ...
        self.rep_counter = RepCounterMediaPipe()
        self.current_exercise = None
    
    def process_frame(self, frame, landmarks):
        # ... existing processing ...
        
        # NEW: Detect rep
        if isinstance(landmarks, list):
            landmarks = np.array(landmarks)
        
        rep_detected = self.rep_counter.count_rep(landmarks, self.current_exercise)
        
        return {
            'landmarks': landmarks.tolist(),
            'rep_detected': rep_detected,
            'rep_count': self.rep_counter.rep_count,
            'form_status': form_status,
            'feedback': feedback
        }
```

### 4.2 Update: `main.py`

Add API endpoint:

```python
@app.route('/api/session/landmarks', methods=['GET'])
def get_landmarks():
    """Return landmarks and feedback for frontend"""
    session_data = get_current_session()  # Your session retrieval method
    
    if session_data and session_data.get('latest_landmarks'):
        return jsonify({
            'landmarks': session_data['latest_landmarks'],
            'form_status': session_data.get('form_status'),
            'feedback': session_data.get('feedback'),
            'rep_detected': session_data.get('rep_detected', False),
        })
    
    return jsonify({'error': 'No session'}), 404
```

---

## Step 5: Test Everything (10 minutes)

### 5.1 Browser Console Test

Open DevTools (F12) and paste:

```javascript
// Test gamification engine
const engine = new GamificationEngine();
engine.recordRep(true);
console.log('Reps:', engine.repCount); // Should be 1
console.log('Streak:', engine.streak); // Should be 1
console.log('Message:', engine.getMotivationalMessage());

// Test skeleton visualizer
const skeleton = new SkeletonVisualizer('skeletonCanvas');
const testLandmarks = Array(33).fill([0.5, 0.5, 0.9]);
skeleton.draw(testLandmarks);
console.log('Skeleton initialized');

// Test UI
const ui = new GamificationUI(engine, 'gamification-container');
console.log('UI initialized');
```

**Expected Output**:
```
Reps: 1
Streak: 1
Message: "Great! You've completed your first rep!"
Skeleton initialized
UI initialized
```

### 5.2 Visual Inspection

Navigate to session page and check:
- [ ] Canvas appears (dark area on left)
- [ ] GIF section shows on center
- [ ] Gamification cards on right
- [ ] Rep counter shows "0"
- [ ] Badges are visible
- [ ] Progress ring displays
- [ ] Form status indicator visible

### 5.3 Functionality Test

With camera running:
- [ ] Skeleton draws your posture in real-time
- [ ] Colors change (head=blue, arms=yellow, legs=red)
- [ ] Form status indicator updates
- [ ] Rep counter increments on good form

---

## 🔧 Troubleshooting

### Canvas Not Showing
```javascript
// Check in console:
const canvas = document.getElementById('skeletonCanvas');
console.log('Canvas:', canvas); // Should not be null

// Verify size
console.log('Size:', canvas.width, canvas.height); // Should be 300x400
```

**Fix**: Ensure canvas element exists in HTML
```html
<canvas id="skeletonCanvas" class="skeleton-canvas" width="300" height="400"></canvas>
```

### Landmarks Not Updating
```javascript
// Check API endpoint
fetch('/api/session/landmarks')
    .then(r => r.json())
    .then(d => console.log(d));

// Should return: {landmarks: [...], form_status: '...', ...}
```

**Fix**: Ensure `/api/session/landmarks` endpoint exists in Flask

### Gamification Not Initializing
```javascript
// Check container exists
const container = document.getElementById('gamification-container');
console.log('Container:', container); // Should not be null

// Try manual initialization
const engine = new GamificationEngine();
const ui = new GamificationUI(engine, 'gamification-container');
console.log('UI initialized:', ui);
```

**Fix**: Ensure `gamification-container` div exists in HTML

### Rep Counter Not Detecting
```python
# Check in Python console
from rep_counter_mediapipe import RepCounterMediaPipe
counter = RepCounterMediaPipe()

# Test with dummy landmarks
import numpy as np
landmarks = np.random.rand(33, 3)
result = counter.count_rep(landmarks, 'squat')
print('Rep detected:', result)
```

**Fix**: Ensure landmarks are 33x3 numpy array with confidence values 0-1

---

## ✅ Verification Checklist

Before considering complete:

```
Frontend:
☐ All CSS loads (no 404 in console)
☐ All JS loads (no 404 in console)
☐ No JavaScript errors (console clean)
☐ Canvas renders without errors
☐ Gamification container renders

Visual:
☐ Skeleton canvas visible (dark)
☐ Rep counter shows "0"
☐ Badges display (10 visible)
☐ Progress ring visible
☐ Streak container visible
☐ Form status indicator visible
☐ GIF section visible
☐ Layout is 3-column on desktop

Functional:
☐ Skeleton updates with landmarks
☐ Rep counter increments on good form
☐ Badges unlock at milestones
☐ Form status shows correct/incorrect
☐ Progress ring animates
☐ Sound works (optional)

Backend:
☐ `/api/session/landmarks` endpoint works
☐ Rep counter initializes without errors
☐ Landmarks returned in API response
☐ Form status returned in API response
```

---

## 🎯 Quick Reference

### Key Files Modified

| File | Changes | Status |
|------|---------|--------|
| `templates/patient/session.html` | Added 3-column layout, scripts | Required |
| `static/session.js` | Added initialization, polling | Required |
| `Rehab_Scorer_Coach/src/web_pipeline.py` | Added rep counter | Required |
| `Rehab_Scorer_Coach/src/keraal_pipeline.py` | Added rep counter | Required |
| `main.py` | Added `/api/session/landmarks` | Required |

### New Files Added

| File | Purpose | Size |
|------|---------|------|
| `Rehab_Scorer_Coach/src/rep_counter_mediapipe.py` | Rep detection | 350 lines |
| `static/skeleton_visualization.js` | Pose rendering | 250 lines |
| `static/gamification.js` | Game logic | 700 lines |
| `static/gamified_ui.css` | Styling | 450 lines |

### Environment Variables (Optional)

```bash
# .env or config
ENABLE_SOUND_EFFECTS=true        # Default: true
DAILY_CHALLENGE_GOAL=20          # Default: 20
ENABLE_GAMIFICATION=true         # Default: true
```

---

## 📱 Mobile Testing

Test on mobile device:

```bash
# On your machine:
python -m http.server 8000

# On mobile, visit:
http://<YOUR_IP>:5000/patient/session
```

Check:
- [ ] Layout stacks vertically (1 column)
- [ ] Canvas responsive to screen size
- [ ] Touch events work (if applicable)
- [ ] No layout breaks

---

## 🎮 Test Rep Detection Manually

### Squat Test
1. Start exercise: "squat"
2. Stand in front of camera
3. Slowly bend knees to 90°
4. Slowly stand back up
5. Watch for: Rep counter increments

### Arm Raise Test
1. Start exercise: "lifting_of_arms"
2. Raise arms slowly overhead
3. Lower arms slowly
4. Watch for: Rep counter increments

### Streak Test
1. Complete 5 reps with correct form
2. Watch badge unlock: ✨ Perfect Form

---

## 🚀 Next Steps After Setup

### Immediate (30 min)
1. ✅ Get everything working
2. ✅ Test all features
3. ✅ Verify mobile responsive

### Short Term (1-2 hours)
1. Fine-tune rep detection accuracy
2. Add more exercise GIFs
3. Optimize performance
4. Add sound effects (if desired)

### Medium Term (1-2 days)
1. User testing with real patients
2. Gather feedback on gamification
3. Adjust difficulty thresholds
4. Deploy to production

### Long Term (1-2 weeks)
1. Monitor user engagement metrics
2. Iterate on achievement system
3. Add personalization
4. Collect performance data

---

## 📊 Success Metrics

Track after deployment:

```
Rep Counter Accuracy:
├── Target: >95% match vs manual
├── Measure: Compare 10 test sets
└── Expected: ±1-2 reps variance

User Engagement:
├── Average session reps: target 15-20
├── Badge unlock rate: target 2-3 per session
├── Daily return rate: target >60%
└── Form quality improvement: +5% per week

Performance:
├── Skeleton FPS: target 60
├── API response: target <200ms
├── Page load: target <3s
└── Memory: stable <50MB
```

---

## 🐛 Common Gotchas

1. **Landmarks not 33-length**: Verify MediaPipe model returns 33 joints
2. **Canvas size issue**: Set width/height attributes (not CSS)
3. **CORS errors**: If APIs from different domain, add CORS headers
4. **LocalStorage blocked**: Check browser privacy settings
5. **Audio context fails**: Some browsers require user interaction first

---

## 📞 Quick Help

### "Rep counter not detecting"
→ Ensure full body visible, good lighting, landmarks have confidence >0.5

### "Canvas is blank"
→ Check `skeletonCanvas` ID in HTML, ensure canvas width/height set

### "Gamification cards not appearing"
→ Check `gamification-container` exists, verify JS no errors in console

### "API returning 404"
→ Ensure `/api/session/landmarks` endpoint defined in Flask, method is GET

### "Mobile layout broken"
→ Check CSS media queries working, use Chrome DevTools device emulation

---

## ✨ You're Done!

If all checkboxes are complete, the gamified UI is live! 🎉

### What Users See:
- ✅ Real-time skeleton of their pose
- ✅ Exercise form demonstration (GIF)
- ✅ Rep counter with animations
- ✅ Achievement badges unlocking
- ✅ Streak counter with fire emoji
- ✅ Daily progress tracking
- ✅ Form quality feedback
- ✅ Motivational messages

### What Happens Next:
1. Patient uses feature
2. Engagement increases
3. Form quality improves
4. Achievements motivate
5. Habit formation begins
6. Better rehabilitation outcomes

---

**Total Setup Time**: 30 minutes
**Result**: Fully gamified rehabilitation experience
**Status**: ✅ Ready to Deploy

Good luck! 🚀
