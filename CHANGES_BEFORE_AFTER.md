# Quick Reference - Code Changes Made

## File: templates/patient/session.html

### Change 1: Score Display Gate Handling (Line 798-807)

**BEFORE:**
```javascript
function updateFormStatus(status, score) {
    const badge = document.getElementById('formStatusBadge');
    const scoreText = document.getElementById('frameScoreText');
    scoreText.textContent = Number(score || 0).toFixed(1);
    allScores.push(Number(score || 0));
    // ... rest of function
}
```

**AFTER:**
```javascript
function updateFormStatus(status, score) {
    const badge = document.getElementById('formStatusBadge');
    const scoreText = document.getElementById('frameScoreText');
    
    // Only update score if it's non-zero (0.0 is from display gate)
    // Keep previous score when gate is active
    if (score && score > 0) {
        scoreText.textContent = Number(score).toFixed(1);
        allScores.push(Number(score));
    }
    // ... rest of function
}
```

**Why**: Skip updates when frame_score=0.0 (display gate inactive)

---

### Change 2: Form Status Check - Badge Display (Line 815)

**BEFORE:**
```javascript
} else if (status === 'WRONG') {
    badge.className = 'badge incorrect';
    badge.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> FORM NEEDS WORK';
```

**AFTER:**
```javascript
} else if (status === 'INCORRECT') {
    badge.className = 'badge incorrect';
    badge.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> FORM NEEDS WORK';
```

**Why**: Backend returns "INCORRECT", not "WRONG"

---

### Change 3: Add WARMUP Status (Line 820)

**BEFORE:**
```javascript
} else {
    badge.className = 'badge analyzing';
    badge.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> ANALYZING...';
}
```

**AFTER:**
```javascript
} else if (status === 'WARMUP') {
    badge.className = 'badge analyzing';
    badge.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> WARMING UP...';
} else {
    badge.className = 'badge analyzing';
    badge.innerHTML = '<i class="fa-solid fa-hourglass-half"></i> ANALYZING...';
}
```

**Why**: Handle WARMUP status from backend

---

### Change 4: Add Debug Logging to TTS (Line 956-989)

**BEFORE:**
```javascript
async function playNextTTS() {
    if (ttsQueue.length === 0) { isSpeaking = false; return; }
    isSpeaking = true;
    const text = ttsQueue.shift();
    try {
        const res = await fetch(API_BASE + '/api/tts', {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, language: getLanguageName() })
        });
        if (!res.ok) throw new Error("TTS HTTP " + res.status);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        ttsAudio = new Audio(url);
        ttsAudio.playbackRate = 1.25;
        ttsAudio.onended = function() { URL.revokeObjectURL(url); playNextTTS(); };
        await ttsAudio.play();
    } catch (e) {
        console.error("Server TTS failed, using browser fallback:", e);
        if ('speechSynthesis' in window) {
            const u = new SpeechSynthesisUtterance(text);
            u.rate = 1.0; u.pitch = 1.0;
            u.onend = function() { playNextTTS(); };
            window.speechSynthesis.speak(u);
        } else {
            isSpeaking = false;
        }
    }
}
```

**AFTER:**
```javascript
async function playNextTTS() {
    if (ttsQueue.length === 0) { isSpeaking = false; return; }
    isSpeaking = true;
    const text = ttsQueue.shift();
    console.log(`[TTS] Playing: "${text}" | audioEnabled=${audioEnabled}`);
    try {
        const lang = getLanguageName();
        console.log(`[TTS] Calling /api/tts with language: ${lang}`);
        const res = await fetch(API_BASE + '/api/tts', {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text, language: lang })
        });
        console.log(`[TTS] Response status: ${res.status}`);
        if (!res.ok) throw new Error("TTS HTTP " + res.status);
        const blob = await res.blob();
        console.log(`[TTS] Blob received: ${blob.size} bytes`);
        const url = URL.createObjectURL(blob);
        ttsAudio = new Audio(url);
        ttsAudio.playbackRate = 1.25;
        ttsAudio.onended = function() { 
            console.log(`[TTS] Audio ended, playing next`);
            URL.revokeObjectURL(url); 
            playNextTTS(); 
        };
        console.log(`[TTS] Playing audio...`);
        await ttsAudio.play();
        console.log(`[TTS] Audio play() called successfully`);
    } catch (e) {
        console.error("[TTS] Server TTS failed, using browser fallback:", e);
        if ('speechSynthesis' in window) {
            const u = new SpeechSynthesisUtterance(text);
            u.rate = 1.0; u.pitch = 1.0;
            u.onend = function() { 
                console.log(`[TTS] Browser speech ended, playing next`);
                playNextTTS(); 
            };
            console.log(`[TTS] Using browser speechSynthesis...`);
            window.speechSynthesis.speak(u);
        } else {
            console.error("[TTS] Browser speechSynthesis not available");
            isSpeaking = false;
        }
    }
}
```

**Why**: Add detailed debugging for TTS pipeline

---

### Change 5: Add Debug Logging to Queue Speech (Line 1004-1017)

**BEFORE:**
```javascript
function queueSpeech(text) {
    if (!text || !audioEnabled) return;
    ttsQueue.push(text);
    if (!isSpeaking) playNextTTS();
}

async function speakFeedbackList(items) {
    if (!items || items.length === 0 || !audioEnabled) return;
    const now = Date.now();
    if (now - lastSpokenAt < SPEAK_COOLDOWN_MS) return;
    const hash = items.join("|");
    if (hash === lastSpokenHash) return;
    queueSpeech(items.slice(0, 2).join(". "));
    lastSpokenHash = hash;
    lastSpokenAt = now;
}
```

**AFTER:**
```javascript
function queueSpeech(text) {
    if (!text || !audioEnabled) {
        console.log(`[TTS] queueSpeech skipped: text="${text}", audioEnabled=${audioEnabled}`);
        return;
    }
    console.log(`[TTS] queueSpeech: Adding "${text}" to queue`);
    ttsQueue.push(text);
    if (!isSpeaking) {
        console.log(`[TTS] Not speaking, calling playNextTTS`);
        playNextTTS();
    }
}

async function speakFeedbackList(items) {
    console.log(`[TTS] speakFeedbackList called with:`, items);
    if (!items || items.length === 0 || !audioEnabled) {
        console.log(`[TTS] speakFeedbackList skipped: items=${items}, audioEnabled=${audioEnabled}`);
        return;
    }
    const now = Date.now();
    if (now - lastSpokenAt < SPEAK_COOLDOWN_MS) {
        console.log(`[TTS] Cooldown active: ${SPEAK_COOLDOWN_MS - (now - lastSpokenAt)}ms remaining`);
        return;
    }
    const hash = items.join("|");
    if (hash === lastSpokenHash) {
        console.log(`[TTS] Duplicate feedback, skipping`);
        return;
    }
    const textToSpeak = items.slice(0, 2).join(". ");
    console.log(`[TTS] Speaking feedback: "${textToSpeak}"`);
    queueSpeech(textToSpeak);
    lastSpokenHash = hash;
    lastSpokenAt = now;
}
```

**Why**: Debug voice queue management

---

### Change 6: Fix Voice Trigger - Check Status (Line 1119)

**BEFORE:**
```javascript
        if (out.form_status === "WRONG" && fb && fb.length > 0) {
            await speakFeedbackList(fb);
        }
```

**AFTER:**
```javascript
        console.log(`[pollFeedback] form_status=${out.form_status}, feedback=${fb}, length=${fb ? fb.length : 0}`);
        if (out.form_status === "INCORRECT" && fb && fb.length > 0) {
            console.log(`[pollFeedback] Calling speakFeedbackList with:`, fb);
            await speakFeedbackList(fb);
        } else if (out.form_status === "INCORRECT") {
            console.log(`[pollFeedback] INCORRECT form but no feedback: fb=${fb}`);
        }
```

**Why**: 
1. Fix status check: "WRONG" → "INCORRECT"
2. Add debugging to see feedback flow

---

## Summary of Changes

| Location | Type | Count |
|----------|------|-------|
| Score display gate | Logic fix | 1 |
| Status checks | Value fix | 2 |
| TTS playback logging | Debug logging | 8 lines |
| Queue speech logging | Debug logging | 12 lines |
| Feedback logging | Debug logging | 5 lines |
| **Total** | **Combined** | **~35 lines** |

---

## Impact

| Change | Impact | Severity |
|--------|--------|----------|
| Score gate handling | Score now displays correctly | CRITICAL |
| Status value fix | Voice now triggers | CRITICAL |
| Debug logging | Can now debug issues | IMPORTANT |

---

## Testing

After applying changes:

1. **Check score displays every 10-15 seconds** (not every frame)
2. **Check voice plays on INCORRECT form** (not CORRECT form)
3. **Check console for [TTS] messages** (for debugging)

---

## Rollback

If needed to revert, restore original versions:
- All changes in: `templates/patient/session.html`
- Only file modified
- No other files affected

