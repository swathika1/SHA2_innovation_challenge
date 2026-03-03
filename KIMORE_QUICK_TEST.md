# KIMORE Fixes - Quick Testing Guide

## Before You Start
1. ✅ Groq API key set: `export GROQ_API_KEY=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`
2. ✅ Flask server ready to run
3. ✅ Browser console open (F12 or Cmd+Option+I)
4. ✅ Server logs visible (terminal)

---

## 5-Minute Test Plan

### Step 1: Start Server (1 min)
```bash
cd /Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge
export GROQ_API_KEY=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
python main.py
# Should see "Running on http://127.0.0.1:5000"
```

### Step 2: Open Browser & Start Session (1 min)
- Navigate to `http://localhost:5000`
- Login as patient
- Click "KIMORE" (WebRehabPipeline)
- Open browser console (F12 → Console tab)
- Keep server terminal visible

### Step 3: Test Issue #1 - TTS Gating (1.5 min)
**Action**: Perform exercise with INCORRECT form (bend knees incorrectly)
- **Immediately**: Hear TTS audio feedback
- **Wait**: Count 12 seconds while continuing bad form
- **Then**: Hear TTS audio again (NOT before 12 seconds)
- **Console Check**: Should see:
  ```
  [pollFeedback] ✅ Speaking feedback
  [pollFeedback] Feedback ready but in cooldown (55 frames remaining)
  [pollFeedback] Feedback ready but in cooldown (54 frames remaining)
  ...
  ```

### Step 4: Test Issue #2 - Status Gating (1 min)
**Action**: Perform exercise with varying form quality (good → bad → good)
- **Watch**: CORRECT/INCORRECT badge
- **NOT**: Should NOT flicker rapidly
- **Should**: Update smoothly when form actually changes
- **Console**: Should see:
  ```
  [Status Update] Changed: CORRECT at score 38.2
  [Status Update] Changed: INCORRECT at score 31.5
  ```

### Step 5: Test Issue #3 - Language Support (1.5 min)
**Action**: Change language to Tamil and repeat exercise
1. Stop current session
2. Go back to main menu
3. Click "Language Settings"
4. Select "Tamil"
5. Start KIMORE again
6. Perform exercise with INCORRECT form
7. **Critical**: TTS should speak in Tamil
8. **Console Check**: Should see:
   ```
   [LLM] Raw response (Tamil): வணக்கம் நன்றி...
   [LLM] Parsed 3 feedback items in Tamil
   ```

---

## 30-Minute Deep Test Plan

### Detailed TTS Test
```
Time  Action                     Expected Result
----  ------                     ---------------
0:00  Start bad form             Audio plays immediately
0:12  Still bad form             Audio plays again
0:24  Still bad form             Audio plays third time (12sec interval confirmed)
0:15  Fix form (CORRECT)         Audio stops
0:30  Bad form again             Audio resumes immediately
```

### Detailed Status Test
```
Score  Status      Badge Change  Console
-----  ------      -----------    -------
35.2   CORRECT     → ✓            [Status Update] Changed: CORRECT
34.8   CORRECT     -              (no change, diff < 0.5)
34.3   CORRECT     -              (no change, diff < 0.5)
33.6   INCORRECT   → ✗            [Status Update] Changed: INCORRECT
```

### Detailed Language Test
```
Language  Expected Output           Not Acceptable
--------  ----------------          ---------------
Tamil     "முறை சரியாக இல்லை..."    "Form is incorrect..." (English)
Chinese   "动作不正确..."             Mixed English/Chinese
Malay     "Bentuk tidak betul..."    English instructions
```

### Detailed RAG Test
```
Server Log Check:
✅ "RAG retrieved 3 relevant context items"
✅ "LLM feedback generated in [language]"

LLM Feedback Quality:
✅ Mentions specific exercise (e.g., "knee bend angle")
✅ References form corrections
✅ Action-oriented tips
✗ Generic: "Keep posture controlled" (fallback only)
```

---

## Console Log Reference

### Expected Console Messages

**TTS Gating (every 12 seconds when INCORRECT)**
```javascript
[pollFeedback] ✅ Speaking feedback (cooldown active: true)
[pollFeedback] Feedback ready but in cooldown (59 frames remaining)
[pollFeedback] Feedback ready but in cooldown (58 frames remaining)
...
[pollFeedback] Feedback ready but in cooldown (0 frames remaining)
[pollFeedback] ✅ Speaking feedback (cooldown active: true)
```

**Status Gating (when score changes >0.5)**
```javascript
[Status Update] Changed: CORRECT at score 38.2
[Status Update] Changed: INCORRECT at score 31.5
```

**LLM Language Support**
```python
[LLM] Raw response (Tamil): வணக்கம் நன்றி...
[LLM] Parsed 3 feedback items in Tamil

# Or for other languages:
[LLM] Raw response (Chinese): 你好，感谢...
[LLM] Parsed 2 feedback items in Chinese
```

**RAG Context Retrieval**
```python
✅ RAG retrieved 3 relevant context items
✅ LLM feedback generated in Tamil: [feedback list]

# Or if RAG fails:
⚠️  RAG returned no results, using fallback
⚠️  RAG failed: [error message]
```

---

## Common Issues & Quick Fixes

| Issue | Signs | Fix |
|-------|-------|-----|
| TTS Playing Every Frame | Console shows no "cooldown" messages | Verify `feedbackSpokenCooldown` is decrementing |
| Status Flickering | Badge changes every 0.1-0.2 sec | Increase `STATUS_UPDATE_THRESHOLD` to 1.0 |
| Tamil Still English | "[LLM] Raw response (Tamil):" shows English | Check language parameter spelling exactly "Tamil" |
| No RAG Context | No feedback improvement, generic text | Check RAG database initialized, verify queries not failing |
| Audio Not Playing | No sound even first time | Check browser audio enabled, volume on, speaker working |

---

## Performance Indicators

**Good Signs** ✅
- TTS audio every ~12 seconds (not on every frame)
- Status badge updates smoothly (<1 update per second)
- Console shows "[LLM] Raw response (Tamil):" with Tamil text
- Server shows "RAG retrieved 3 relevant context items"
- Feedback is exercise-specific (mentions form corrections)

**Bad Signs** ❌
- Audio plays constantly/every frame
- Badge flickers between CORRECT/INCORRECT
- Feedback always in English
- No "[LLM] Raw response" messages
- Feedback is generic ("Keep posture controlled")

---

## Quick Rollback (If Issues Found)

All changes are in these files:
1. `templates/patient/session.html` - Lines 581-591, 815-845, 1142-1149
2. `Rehab_Scorer_Coach/src/llm_groq.py` - Lines 143, 150-171, 187-194
3. `Rehab_Scorer_Coach/src/web_pipeline.py` - Lines 320-380

Can revert individual sections if needed.

---

## Success Criteria

✅ **All tests pass if:**
1. TTS audio plays ~every 12 seconds, not every frame
2. Status badge is stable, doesn't flicker
3. Feedback language matches selected language (Tamil, Chinese, etc.)
4. Feedback includes exercise-specific cues (not generic)
5. No console errors or exceptions

✅ **Test passes with these console messages:**
- `[pollFeedback] Feedback ready but in cooldown`
- `[Status Update] Changed:`
- `[LLM] Raw response (Tamil):`
- `✅ RAG retrieved 3 relevant context items`

---

## Time Estimates

- **Quick Test (Issue Confirmation)**: 5 minutes
- **Full Test (All 4 Issues)**: 15-20 minutes  
- **Deep Dive (Language + RAG Quality)**: 30+ minutes

---

## Next Actions After Testing

1. **If All Pass**: System ready for production ✅
2. **If TTS Failing**: Check `feedbackSpokenCooldown` logic
3. **If Status Flickering**: Increase `STATUS_UPDATE_THRESHOLD` 
4. **If Language Wrong**: Verify language parameter and LLM response
5. **If RAG Not Working**: Check RAG database and queries

---

**Happy Testing!** 🚀

For detailed information, see: `KIMORE_FIXES_SUMMARY.md`
