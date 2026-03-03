# Verification Checklist - Score & Voice Fixes ✅

## Pre-Flight Checks

- [ ] Flask server is running: `python3 main.py`
- [ ] No errors in terminal
- [ ] Browser is open to the application
- [ ] Developer Tools available (F12)

---

## Test 1: Score Display Gate

### Setup
1. Open browser → Patient Session
2. Open DevTools Console (F12 → Console)
3. Filter by: `[pollFeedback]`
4. Start exercise

### Test Case: CORRECT Form
```
EXPECTED:
  - Form status badge shows: "✓ CORRECT FORM" (green)
  - Score box shows: "--" or previous value (NOT "0.0")
  - Console shows: form_status=CORRECT, feedback=[]
```

**Result**: ☐ PASS / ☐ FAIL

### Test Case: INCORRECT Form (wait 10-15 sec)
```
EXPECTED:
  - Form status badge shows: "✗ FORM NEEDS WORK" (red)
  - After 10-15 seconds:
    - Terminal shows: "📊 Score Display Update: XX.XX/50"
    - UI score box updates to show: "XX.X"
    - Console shows: form_status=INCORRECT, feedback=[...]
```

**Result**: ☐ PASS / ☐ FAIL

### Console Output Check
```
Expected in Console:
[pollFeedback] form_status=CORRECT, feedback=[], length=0
[pollFeedback] form_status=INCORRECT, feedback=["Your form..."], length=1
```

**Result**: ☐ PASS / ☐ FAIL

---

## Test 2: Voice/TTS Playback

### Setup
1. Keep DevTools open
2. Filter Console by: `[TTS]`
3. Make sure speakers are NOT muted
4. Check browser tab permissions (look for speaker icon)

### Test Case: Audio Disabled (OFF)
```
Steps:
  1. Check "Voice Feedback: OFF"
  2. Perform INCORRECT form
  3. Wait 10-15 seconds
  
EXPECTED:
  - No audio plays
  - Console shows: [TTS] speakFeedbackList skipped: ... audioEnabled=false
  - Score still displays (score gate = independent)
```

**Result**: ☐ PASS / ☐ FAIL

### Test Case: Audio Enabled (ON)
```
Steps:
  1. Click "Toggle" button → "Voice Feedback: ON"
  2. Perform INCORRECT form
  3. Wait 10-15 seconds
  
EXPECTED:
  - Audio plays automatically (you hear voice feedback)
  - Console shows full TTS sequence
```

**Result**: ☐ PASS / ☐ FAIL

---

## Test 3: Multiple Feedback Cycles

### Setup
1. Perform exercise for 30+ seconds
2. Switch between correct and incorrect form multiple times

### Test Case: Multiple Feedback Cycles
```
EXPECTED:
  - Score updates every 10-15 seconds
  - Voice plays every 10-15 seconds when form is INCORRECT
  - Cooldown prevents same feedback twice in a row
  - No audio stacking/overlap
```

**Result**: ☐ PASS / ☐ FAIL

---

## Summary Scoring

### Critical Features (Must Pass)
- [ ] Score displays correctly (every 10-15 sec)
- [ ] Voice plays on INCORRECT form
- [ ] Status badge shows correct values (CORRECT/INCORRECT)
- [ ] Audio toggle works (ON/OFF)

**Critical Score**: ☐ 4/4 PASS ✅

### Important Features (Should Pass)
- [ ] Feedback is exercise-specific
- [ ] Cooldown prevents feedback spam
- [ ] Multiple cycles work smoothly
- [ ] Language selection works

**Important Score**: ☐ 4/4 PASS ✅

---

## Troubleshooting Guide

### No Score Showing
1. Check: Is score > 0? (0.0 is filtered)
2. Check: Is form INCORRECT?
3. Check: Has 10-15 seconds passed?
4. Check Terminal: "📊 Score Display Update" messages?

### No Voice Playing
1. Check: audioEnabled = true in console
2. Check: form_status = "INCORRECT"?
3. Check: feedback is not empty?
4. Check: [TTS] messages in console?
5. Check: Browser audio permissions?
6. Check: System volume not muted?

### Wrong Status Showing
1. Check: Status is "CORRECT" or "INCORRECT" (not "WRONG")
2. Check Console: form_status value in [pollFeedback] messages

---

## Files Modified

✅ `templates/patient/session.html`
- Score display gate handling (line 798-807)
- Status check: "WRONG" → "INCORRECT" (lines 815, 1119)
- Added console logging for debugging

---

## Final Status

```
☐ All critical tests PASS
☐ Score displays every 10-15 seconds  
☐ Voice plays on incorrect form
☐ Status badge shows correct values
☐ No console errors

SYSTEM STATUS: ✅ READY TO TEST
```

See `DEBUGGING_SCORE_AND_VOICE.md` and `SCORE_VOICE_FIXES_SUMMARY.md` for detailed information.

