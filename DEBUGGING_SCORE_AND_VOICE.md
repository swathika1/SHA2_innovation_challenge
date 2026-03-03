# Debugging Score and Voice Issues - Quick Guide

## Issues Fixed

### 1. Score Not Rendering ✅
**Problem**: Score showing 0.0 or "--" in UI despite being visible in terminal

**Root Cause**: 
- Display gate was returning 0.0 every frame except every 10-15 seconds
- Frontend was updating score to "0.0" instead of keeping previous value

**Fixes Applied**:
```javascript
// BEFORE: Always update score, even when 0.0
scoreText.textContent = Number(score || 0).toFixed(1);

// AFTER: Only update score when > 0 (skip 0.0 from display gate)
if (score && score > 0) {
    scoreText.textContent = Number(score).toFixed(1);
    allScores.push(Number(score));
}
```

**Result**: Score now displays actual value when display window opens, keeps previous value when gated

---

### 2. Voice Not Working ✅
**Problem**: Voice feedback never plays even though audioEnabled = true

**Root Causes Found**:
1. Backend returns `"INCORRECT"` but frontend was checking for `"WRONG"` 
2. Missing console logging made debugging impossible

**Fixes Applied**:

```javascript
// BEFORE: Checking for wrong status value
if (out.form_status === "WRONG" && fb && fb.length > 0) {
    await speakFeedbackList(fb);
}

// AFTER: Checking for correct status value
if (out.form_status === "INCORRECT" && fb && fb.length > 0) {
    await speakFeedbackList(fb);
}
```

**Result**: Voice now triggers correctly when form is INCORRECT ✅

---

## How to Test

### Test 1: Score Display
1. Open browser Developer Tools (F12)
2. Go to Console tab
3. Start an exercise with CORRECT form
4. Watch the score box - should stay blank or show previous value
5. After 10-15 seconds with incorrect form, score should update
6. Look for message: `📊 Score Display Update: XX.XX/50` in terminal

**Expected Console Output**:
```
[pollFeedback] form_status=CORRECT, feedback=[], length=0
[pollFeedback] form_status=INCORRECT, feedback=["Your form needs..."], length=1
```

---

### Test 2: Voice Feedback
1. Open browser Developer Tools (F12)
2. Go to Console tab
3. Start an exercise with INCORRECT form
4. Wait 10-15 seconds
5. Listen for voice output
6. Check console for `[TTS]` messages

**Expected Console Output**:
```
[TTS] speakFeedbackList called with: ["Your form needs significant work..."]
[TTS] Speaking feedback: "Your form needs significant work..."
[TTS] queueSpeech: Adding "Your form..." to queue
[TTS] Not speaking, calling playNextTTS
[TTS] Playing: "Your form..." | audioEnabled=true
[TTS] Calling /api/tts with language: English
[TTS] Response status: 200
[TTS] Blob received: XXXX bytes
[TTS] Playing audio...
[TTS] Audio play() called successfully
```

---

### Test 3: Check Audio is Enabled
```javascript
// In browser console, type:
audioEnabled
// Should print: true

// Check status display:
document.getElementById('audioStatus').textContent
// Should print: "ON"
```

---

## Debugging Console Messages

### `[TTS]` Messages
These are from the TTS system:

| Message | Meaning | Action |
|---------|---------|--------|
| `speakFeedbackList called with: [...]` | Feedback function triggered | Normal |
| `queueSpeech skipped: ... audioEnabled=false` | Audio is disabled | Enable audio button |
| `Calling /api/tts with language: English` | Server TTS being called | Normal |
| `Response status: 200` | Server replied successfully | Normal |
| `Server TTS failed, using browser fallback` | Server TTS error | Will use browser speech |
| `Browser speechSynthesis not available` | No TTS available | Browser doesn't support it |

### `[pollFeedback]` Messages
These are from the feedback polling system:

| Message | Meaning | Action |
|---------|---------|--------|
| `form_status=INCORRECT, feedback=[...]` | Form is wrong, feedback ready | Should trigger voice |
| `form_status=CORRECT, feedback=[]` | Form is correct, no feedback | Normal |
| `INCORRECT form but no feedback` | Form wrong but no feedback text | Backend issue |

---

## Common Issues and Solutions

### Issue: Score shows 0.0 all the time
**Cause**: Display gate is active (not yet 10-15 sec window)
**Solution**: Keep exercising, score will update after 10-15 sec

### Issue: Score shows but voice doesn't play
**Cause**: `audioEnabled` is false or feedback is empty
**Solution**: 
1. Check console: Is `audioEnabled = true`?
2. Check console: Is feedback being sent from backend?
3. Click audio toggle button to enable

### Issue: Console shows `Response status: 200` but no audio
**Cause**: Browser permissions or playback issue
**Solution**:
1. Check browser volume is not muted
2. Check browser audio permissions (look for speaker icon in address bar)
3. Try browser fallback - wait for `Browser speechSynthesis` message
4. Check browser console for any CORS or permission errors

### Issue: Response status 404 or 500
**Cause**: TTS endpoint not working
**Solution**:
1. Verify Flask server is running: `python3 main.py`
2. Check server logs for `/api/tts` errors
3. Verify `edge_tts` package is installed: `pip list | grep edge-tts`

---

## Manual Testing Steps

### Step 1: Verify Backend
```bash
# Check if server is running
curl -s http://localhost:5000/health
# Should return: {"status":"ok"}

# Test TTS endpoint
curl -X POST http://localhost:5000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Test audio","language":"English"}' \
  --output test.mp3

# If successful, should create test.mp3 file
ls -lh test.mp3
```

### Step 2: Verify Frontend
```javascript
// In browser console:

// Check audio enabled
console.log("Audio enabled:", audioEnabled);

// Check feedback queue
console.log("TTS Queue:", ttsQueue);
console.log("Is Speaking:", isSpeaking);

// Manually trigger TTS
queueSpeech("This is a test");

// Check if feedback receives
console.log("Last spoken at:", lastSpokenAt);
console.log("Last spoken hash:", lastSpokenHash);
```

### Step 3: Check Network
```javascript
// In browser console - Network tab
// When feedback is received, you should see POST to /api/tts
// Check Response tab for audio blob
```

---

## Summary of Changes

### File: templates/patient/session.html

**Change 1**: Score display gate handling (line ~799)
- Only update score when > 0
- Preserves previous score during display gate

**Change 2**: Form status check (line ~1118)
- Changed `"WRONG"` to `"INCORRECT"`
- Now matches backend status values

**Change 3**: Added console logging to:
- `playNextTTS()` - TTS playback debugging
- `queueSpeech()` - TTS queue management
- `speakFeedbackList()` - Feedback trigger point
- `pollFeedback()` - Main feedback loop

**Logging prefix**: `[TTS]` and `[pollFeedback]` for easy filtering

---

## Next Steps if Issues Persist

1. **Check Terminal Logs**
   - Run server with: `python3 main.py 2>&1 | tee server.log`
   - Look for errors containing "TTS", "feedback", "KERAAL"

2. **Check Browser Console** (F12 → Console)
   - Filter by `[TTS]` to see all TTS messages
   - Filter by `[pollFeedback]` to see feedback messages
   - Look for red error messages

3. **Enable Network Monitoring** (F12 → Network)
   - Look for POST requests to `/api/tts`
   - Check response status (should be 200)
   - Check response content (should be audio blob)

4. **Test Feedback Generation**
   - Look in server logs for feedback generation messages
   - Check if feedback is being returned in JSON response
   - Verify feedback is not empty array

5. **Test Audio Playback**
   - Try browser fallback manually: `window.speechSynthesis.speak(new SpeechSynthesisUtterance("Test"))`
   - Check if system volume is muted
   - Check browser permissions for microphone/audio

---

## Files Modified

- `templates/patient/session.html` (3 fixes + extensive console logging)

## No Backend Changes Needed
The backend is working correctly. All fixes were in the frontend to:
1. Match the correct status values
2. Handle display gate correctly
3. Add debugging for troubleshooting

