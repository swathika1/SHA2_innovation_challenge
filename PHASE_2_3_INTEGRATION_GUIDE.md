# Phase 2 & 3 Integration Guide: Gamified UI with Rep Counting & Skeleton Visualization

## Overview

This guide explains how to integrate:
1. **Rep Counter** (Backend) - `rep_counter_mediapipe.py`
2. **Skeleton Visualization** (Frontend) - `skeleton_visualization.js`
3. **Gamification Engine** (Frontend) - `gamification.js`
4. **Gamified Styles** (CSS) - `gamified_ui.css`

## Step 1: Update HTML Template

### File: `templates/patient/session.html`

Add the necessary imports and layout structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rehabilitation Session</title>
    
    <!-- Base styles -->
    <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
    
    <!-- GAMIFIED UI STYLES -->
    <link rel="stylesheet" href="{{ url_for('static', filename='gamified_ui.css') }}">
</head>
<body>
    <!-- Main session container -->
    <div class="gradient-bg-green" style="min-height: 100vh; padding: 20px;">
        <div class="container">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 class="gradient-text" style="font-size: 32px;">🏥 Rehabilitation Session</h1>
                <p style="color: var(--text-light);" id="exercise-name">Loading exercise...</p>
            </div>

            <!-- Three-column layout: Skeleton | GIF | Stats -->
            <div class="session-grid">
                
                <!-- LEFT COLUMN: SKELETON VISUALIZATION -->
                <div class="skeleton-section">
                    <div class="gamified-card">
                        <h3 style="margin-top: 0;">👥 Your Posture</h3>
                        <div class="exercise-gif-container">
                            <canvas id="skeletonCanvas" class="skeleton-canvas" width="300" height="400"></canvas>
                            <div style="font-size: 12px; color: var(--text-light); text-align: center;">
                                <p style="margin: 8px 0;">Real-time pose detection</p>
                                <div id="skeleton-status" style="color: var(--success-color);">✓ Detecting</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- CENTER COLUMN: EXERCISE GIF & FORM STATUS -->
                <div class="gif-section">
                    <div class="gamified-card">
                        <h3 style="margin-top: 0;">📹 Correct Form</h3>
                        <div class="exercise-gif-container">
                            <div class="gif-loading-spinner" id="gif-spinner" style="display: none;"></div>
                            <img id="exerciseGif" class="exercise-gif" src="" alt="Exercise demonstration" 
                                 style="display: none;">
                            <div id="no-gif" style="text-align: center; color: var(--text-light);">
                                Loading exercise demonstration...
                            </div>
                        </div>
                    </div>

                    <!-- Form Status Indicator -->
                    <div class="form-status-indicator correct" id="formStatusIndicator" style="display: none;">
                        <span class="form-status-icon" id="formStatusIcon">✓</span>
                        <span id="formStatusText">Good Form!</span>
                    </div>
                </div>

                <!-- RIGHT COLUMN: GAMIFICATION STATS -->
                <div class="stats-section">
                    <!-- This container will be filled by JavaScript -->
                    <div id="gamification-container"></div>
                </div>

            </div>

            <!-- Video Stream (if using camera) -->
            <div style="margin-top: 30px; text-align: center;">
                <div class="gamified-card">
                    <h3 style="margin-top: 0;">📷 Live Camera Feed</h3>
                    <video id="videoInput" width="320" height="240" autoplay playsinline 
                           style="border-radius: 10px; background: #000;"></video>
                </div>
            </div>

        </div>
    </div>

    <!-- SCRIPTS -->
    <!-- Skeleton Visualization -->
    <script src="{{ url_for('static', filename='skeleton_visualization.js') }}"></script>
    
    <!-- Gamification Engine -->
    <script src="{{ url_for('static', filename='gamification.js') }}"></script>
    
    <!-- Session Logic -->
    <script src="{{ url_for('static', filename='session.js') }}"></script>
</body>
</html>
```

## Step 2: Update Session JavaScript

### File: `static/session.js`

This file coordinates all the components:

```javascript
// Global state
let gamificationEngine;
let gamificationUI;
let skeletonVisualizer;

// Exercise GIF database
const exerciseGifs = {
    'squat': 'https://media.giphy.com/media/YOUR_SQUAT_GIF_ID/giphy.gif',
    'lifting_of_arms': 'https://media.giphy.com/media/YOUR_ARMS_GIF_ID/giphy.gif',
    'lateral_trunk_tilt': 'https://media.giphy.com/media/YOUR_TILT_GIF_ID/giphy.gif',
    'trunk_rotation': 'https://media.giphy.com/media/YOUR_ROTATION_GIF_ID/giphy.gif',
    'forward_flexion': 'https://media.giphy.com/media/YOUR_FLEXION_GIF_ID/giphy.gif',
    'flank_stretch': 'https://media.giphy.com/media/YOUR_STRETCH_GIF_ID/giphy.gif',
    'torso_rotation': 'https://media.giphy.com/media/YOUR_TORSO_GIF_ID/giphy.gif',
    'pelvis_rotation': 'https://media.giphy.com/media/YOUR_PELVIS_GIF_ID/giphy.gif',
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize gamification engine
    gamificationEngine = new GamificationEngine();
    gamificationUI = new GamificationUI(gamificationEngine, 'gamification-container');

    // Initialize skeleton visualizer
    skeletonVisualizer = new SkeletonVisualizer('skeletonCanvas');

    // Start polling for session data
    startSessionPolling();
});

/**
 * Poll the backend for landmarks and form feedback
 */
function startSessionPolling() {
    const exerciseName = document.getElementById('exercise-name').textContent;
    
    setInterval(async () => {
        try {
            // Fetch landmarks and form feedback from backend
            const response = await fetch('/api/session/landmarks', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.landmarks && data.landmarks.length > 0) {
                // Draw skeleton
                skeletonVisualizer.draw(data.landmarks);

                // Update form status
                updateFormStatus(data.form_status, data.feedback);

                // Check for rep detection (if backend tracks it)
                if (data.rep_detected) {
                    const result = gamificationEngine.recordRep(data.form_status === 'CORRECT' || data.form_status === 'CORRECT');
                    
                    // Update UI
                    gamificationUI.updateRepCounter(
                        result.repCount, 
                        gamificationEngine.getMotivationalMessage()
                    );
                    gamificationUI.updateStreak(result.streak);
                    gamificationUI.updateProgressRing(gamificationEngine.dailyChallenge.current / gamificationEngine.dailyChallenge.goal);

                    // Unlock new badges
                    result.newBadges.forEach(badge => {
                        gamificationUI.unlockBadgeUI(badge.key);
                    });

                    // Update stats
                    const stats = gamificationEngine.getSessionStats();
                    gamificationUI.updateStats(stats);
                }
            }
        } catch (error) {
            console.error('Error fetching landmarks:', error);
        }
    }, 200); // 5 FPS polling
}

/**
 * Update form status indicator
 */
function updateFormStatus(status, feedback) {
    const indicator = document.getElementById('formStatusIndicator');
    const icon = document.getElementById('formStatusIcon');
    const text = document.getElementById('formStatusText');

    if (status === 'CORRECT' || status === 'CORRECT_FORM') {
        indicator.classList.remove('incorrect');
        indicator.classList.add('correct');
        icon.textContent = '✓';
        text.textContent = feedback || 'Good Form!';
    } else if (status === 'WRONG' || status === 'INCORRECT') {
        indicator.classList.remove('correct');
        indicator.classList.add('incorrect');
        icon.textContent = '✗';
        text.textContent = feedback || 'Adjust your form';
    }
    
    indicator.style.display = 'flex';
}

/**
 * Set exercise GIF based on current exercise
 */
function setExerciseGif(exerciseName) {
    const gifUrl = exerciseGifs[exerciseName];
    const gifElement = document.getElementById('exerciseGif');
    const noGif = document.getElementById('no-gif');
    const spinner = document.getElementById('gif-spinner');

    if (gifUrl) {
        spinner.style.display = 'block';
        gifElement.style.display = 'none';
        noGif.style.display = 'none';

        gifElement.onload = () => {
            spinner.style.display = 'none';
            gifElement.style.display = 'block';
        };

        gifElement.src = gifUrl;
    } else {
        noGif.textContent = 'No demonstration available for this exercise';
    }
}
```

## Step 3: Integrate Rep Counter in Backend

### File: `Rehab_Scorer_Coach/src/web_pipeline.py`

```python
from rep_counter_mediapipe import RepCounterMediaPipe
import numpy as np

class WebRehabPipeline:
    def __init__(self):
        # ... existing code ...
        self.rep_counter = RepCounterMediaPipe()
        self.current_exercise = None
    
    def process_frame(self, frame, landmarks):
        """
        Process a single frame and detect reps
        """
        # ... existing pose detection code ...
        
        # Convert landmarks to numpy array if needed
        if isinstance(landmarks, list):
            landmarks = np.array(landmarks)
        
        # Detect rep using MediaPipe rule-based system
        rep_detected = self.rep_counter.count_rep(landmarks, self.current_exercise)
        
        # Return results
        return {
            'landmarks': landmarks.tolist(),
            'rep_detected': rep_detected,
            'rep_count': self.rep_counter.rep_count,
            'form_status': form_status,  # Keep existing form feedback
            'feedback': feedback_message
        }
    
    def set_exercise(self, exercise_name):
        """
        Set the current exercise and reset rep counter
        """
        self.current_exercise = exercise_name
        self.rep_counter.reset()
```

### File: `Rehab_Scorer_Coach/src/keraal_pipeline.py`

```python
from rep_counter_mediapipe import RepCounterMediaPipe
import numpy as np

class KeraalRehabPipeline:
    def __init__(self):
        # ... existing code ...
        self.rep_counter = RepCounterMediaPipe()
        self.current_exercise = None
    
    def process_frame(self, frame, landmarks):
        """
        Process a single frame and detect reps
        """
        # ... existing pose detection code ...
        
        # Convert landmarks to numpy array if needed
        if isinstance(landmarks, list):
            landmarks = np.array(landmarks)
        
        # Detect rep using MediaPipe rule-based system
        rep_detected = self.rep_counter.count_rep(landmarks, self.current_exercise)
        
        # Return results
        return {
            'landmarks': landmarks.tolist(),
            'rep_detected': rep_detected,
            'rep_count': self.rep_counter.rep_count,
            'form_status': form_status,  # Keep existing form feedback
            'feedback': feedback_message
        }
    
    def set_exercise(self, exercise_name):
        """
        Set the current exercise and reset rep counter
        """
        self.current_exercise = exercise_name
        self.rep_counter.reset()
```

## Step 4: Update Backend API Endpoint

### File: `main.py` or relevant route file

```python
@app.route('/api/session/landmarks', methods=['GET'])
def get_landmarks():
    """
    Return current landmarks and form feedback to frontend
    """
    session_data = get_current_session()
    
    if session_data and session_data.get('latest_landmarks'):
        return jsonify({
            'landmarks': session_data['latest_landmarks'],
            'form_status': session_data.get('form_status'),
            'feedback': session_data.get('feedback'),
            'rep_detected': session_data.get('rep_detected', False),
            'rep_count': session_data.get('rep_count', 0),
            'exercise_name': session_data.get('exercise_name', '')
        })
    
    return jsonify({'error': 'No active session'}), 404
```

## Step 5: Find and Add Exercise GIFs

Replace the GIF URLs in `session.js`:

```javascript
const exerciseGifs = {
    'squat': 'https://media.giphy.com/media/xTiTnCS5NUeVw3g0I0/giphy.gif',  // Woman doing squats
    'lifting_of_arms': 'https://media.giphy.com/media/l0ExayQDzrI2xOb8A/giphy.gif',  // Arm raises
    'lateral_trunk_tilt': 'https://media.giphy.com/media/3ohzdKDB7M1CYkSuFO/giphy.gif',  // Side bends
    'trunk_rotation': 'https://media.giphy.com/media/3o7TKGLX1vw8RYi41G/giphy.gif',  // Torso rotations
    'forward_flexion': 'https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif',  // Forward bends
    'flank_stretch': 'https://media.giphy.com/media/3o6Zt6KHxJTbXCnSvu/giphy.gif',  // Side stretches
    'torso_rotation': 'https://media.giphy.com/media/l0HlDy9x8FZo0XO1i/giphy.gif',  // Torso twists
    'pelvis_rotation': 'https://media.giphy.com/media/l0MYsSoA8FifnwI80/giphy.gif',  // Hip rotation
};
```

## Testing Checklist

- [ ] Skeleton visualization renders in canvas
- [ ] Landmarks update in real-time (33 points visible)
- [ ] Different body parts show correct colors (head=blue, torso=green, arms=yellow, legs=red)
- [ ] Rep counter increments when form is correct
- [ ] Badges unlock at milestones (1, 10, 50 reps)
- [ ] Streak counter tracks consecutive correct reps
- [ ] Progress ring fills as daily goal progresses
- [ ] Form status indicator shows correct/incorrect feedback
- [ ] Exercise GIF displays for current exercise
- [ ] Sound effects play (if enabled)
- [ ] All animations smooth and no jank
- [ ] Mobile responsive (test on tablet/phone)
- [ ] Performance: 60 FPS skeleton rendering
- [ ] Performance: 5 FPS polling doesn't block UI

## Performance Optimization Tips

1. **Skeleton Rendering**: Use `requestAnimationFrame` for smooth 60 FPS
2. **Polling**: 200ms intervals (5 FPS) keeps backend/frontend sync without overload
3. **Canvas**: Reuse canvas context, avoid resizing mid-render
4. **Audio**: Limit sound effects to 1 per second max
5. **Gamification**: Update UI only on changes, not every frame

## Next Steps

1. Collect HD GIFs for all 8 exercises
2. Test rep counter accuracy (target >95%)
3. Optimize skeleton rendering performance
4. Add sound effects (optional but recommended)
5. Test on mobile devices
6. Deploy to production

## File Structure Summary

```
Static Files:
├── gamified_ui.css              (NEW - Styles)
├── gamification.js              (NEW - Game logic)
├── skeleton_visualization.js    (NEW - Pose rendering)
└── session.js                   (UPDATED - Integration)

Backend Files:
├── Rehab_Scorer_Coach/src/
│   ├── rep_counter_mediapipe.py (NEW - Rep counting)
│   ├── web_pipeline.py          (UPDATED - Integration)
│   └── keraal_pipeline.py       (UPDATED - Integration)
└── main.py                      (UPDATED - New API endpoint)

Templates:
└── templates/patient/
    └── session.html             (UPDATED - New layout)
```

---

**Total Implementation Time**: ~2-3 hours (including testing)

**Status**: ✅ All components created, ready for integration and testing
