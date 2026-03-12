# Jimmy Avatar Voice Interaction API

## Overview
Real-time voice conversation with Jimmy avatar. Automatically transcribes speech when you stop talking and responds with text-to-speech audio.

## Endpoint
```
POST /patient/avatar/voice
```

## Authentication
Requires login (uses existing session)

## Request Format

### Headers
```
Content-Type: application/json
```

### Body
```json
{
  "audio": "base64-encoded 16-bit PCM audio at 16kHz",
  "language": "English|Chinese|Malay|Tamil|Singlish",
  "history": [
    {
      "role": "user|assistant",
      "content": "message text"
    }
  ]
}
```

**Parameters:**
- **audio** (required): Base64-encoded audio data
  - Format: 16-bit PCM, mono, 16kHz sample rate
  - Generated from WebRTC audio capture
  - Silence detection happens server-side via Voice Activity Detection (VAD)

- **language** (optional): Communication language
  - Default: "English"
  - Options: "English", "Chinese", "Malay", "Tamil", "Singlish"
  - Jimmy responds in this language

- **history** (optional): Previous conversation messages
  - Used for context-aware responses
  - Format: Array of {role, content} objects

## Response Format

### Success Response (200 OK)
```json
{
  "status": "success",
  "transcribed_text": "what the patient said",
  "response": "Jimmy's text response",
  "response_audio": "base64-encoded MP3 audio of Jimmy's voice",
  "vad_available": true
}
```

**Response Fields:**
- **status**: "success" or "error"
- **transcribed_text**: What the patient's speech was converted to
- **response**: Jimmy's text response using Meralion LLM
- **response_audio**: MP3 audio (base64-encoded) that can be played directly in browser
- **vad_available**: Whether WebRTC VAD is available for future requests

### Error Response (400/500)
```json
{
  "status": "error",
  "error": "Error message describing what went wrong"
}
```

## Processing Pipeline

1. **Voice Activity Detection (VAD)**
   - Audio is processed to detect when speech ends
   - Uses WebRTC VAD for accurate silence detection
   - Fallback: Simple energy-based threshold if VAD unavailable
   - Typical response time: 800ms - 1.5s after speech ends

2. **Speech-to-Text**
   - Uses Groq Whisper API for transcription
   - Fallback: Meralion transcription (if available)
   - Supports multiple languages and accents

3. **Context & RAG**
   - Jimmy retrieves relevant exercise knowledge from RAG database
   - Patient performance history is included
   - Responses are personalized to patient's condition and progress

4. **Response Generation**
   - Uses Meralion's LLM for generating Jimmy's response
   - Incorporates RAG context for accuracy
   - Multi-language support (English, Chinese, Malay, Tamil, Singlish)

5. **Text-to-Speech**
   - Edge-TTS (Microsoft Neural) for high quality voices
   - Fallback: Google TTS for robustness
   - Returns as MP3 audio (base64-encoded for easy browser playback)

## Client-Side Integration

### Using the JavaScript Client Library

```html
<!-- Include the client library -->
<script src="/static/js/jimmy_voice.js"></script>

<!-- Create avatar interface -->
<div id="avatar-voice-container"></div>

<script>
// Initialize
const jimmy = new JimmyVoiceInteraction({
    language: 'English',
    silenceDuration: 1000,  // 1s of silence = end of speech
    
    onRecordingStart: () => console.log('Recording...'),
    onRecordingEnd: () => console.log('Processing...'),
    onTranscribed: (text) => console.log('You said:', text),
    onResponse: (text) => console.log('Jimmy says:', text),
    onError: (error) => console.error(error)
});

// Initialize microphone access
await jimmy.initialize();

// Start/stop conversation
document.getElementById('talk-btn').onclick = () => jimmy.startConversation();
</script>
```

### Manual HTTP Request (cURL)

```bash
# Capture audio from microphone
# ffmpeg -f avfoundation -i ":0" -acodec pcm_s16le -ar 16000 -ac 1 audio.wav

# Convert to base64
AUDIO_B64=$(base64 < audio.wav | tr -d '\n')

# Send to endpoint
curl -X POST http://localhost:5000/patient/avatar/voice \
  -H "Content-Type: application/json" \
  -d "{
    \"audio\": \"$AUDIO_B64\",
    \"language\": \"English\",
    \"history\": []
  }"
```

## Response Latency

| Step | Typical Duration |
|------|-----------------|
| VAD (silence detection) | 800ms - 1.5s |
| Transcription (Whisper) | 1-2s |
| Jimmy response generation | 2-4s |
| TTS synthesis | 1-2s |
| **Total end-to-end** | **5-10 seconds** |

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "No speech detected" | Microphone not working or too much silence | Check microphone levels, try speaking louder |
| "Could not transcribe audio" | Audio quality too poor | Reduce background noise, speak clearly |
| "Unauthorized (401)" | Not logged in | Log in first |
| "Forbidden (403)" | Not a patient | Use patient account |
| "TTS service unavailable" | Both Edge-TTS and Google TTS failed | Try again, network issue |

## Features

✅ **Automatic Voice Activity Detection**
- Knows when you stop talking
- No manual "send" button needed
- Configurable silence threshold

✅ **Real-Time Transcription**
- Groq Whisper API for high accuracy
- Multi-language support
- Automatic language detection

✅ **Personalized Responses**
- Uses patient's performance history
- Retrieves relevant exercise guidance from RAG
- Context-aware coaching

✅ **High-Quality Text-to-Speech**
- Natural-sounding AI voices (Microsoft Edge/Google)
- Multiple language options
- Cached responses for performance

✅ **Conversation History**
- Maintains conversation context
- Jimmy remembers previous messages
- Better follow-up responses

## Testing

### Test with cURL

```bash
# Create a test audio file (1s of silence + tone)
python3 -c "
import numpy as np
import wave

sr = 16000
duration = 2
t = np.linspace(0, duration, sr * duration)
audio = (np.sin(2*np.pi*440*t) * 10000).astype(np.int16)

with wave.open('/tmp/test.wav', 'wb') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sr)
    f.writeframes(audio.tobytes())
"

# Convert to base64 and test
base64 /tmp/test.wav > /tmp/test.b64
curl -X POST http://localhost:5000/patient/avatar/voice \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_ID" \
  -d @- << EOF
{
  "audio": "$(cat /tmp/test.b64 | tr -d '\n')",
  "language": "English",
  "history": []
}
EOF
```

### Test with JavaScript

```javascript
// In browser console, after initializing JimmyVoiceInteraction
jimmy.startConversation();  // Will start listening

// After you speak (returns automatically when silence detected)
// Jimmy responds with audio
```

## Performance Optimization

- **Enable webrtcvad**: Auto-installed, provides accurate voice detection
- **Shorter silenceDuration**: 800ms provides good responsiveness (default)
- **Add conversation history**: Improves response quality but increases latency
- **Cache TTS responses**: Identical responses use cached audio

## Browser Compatibility

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ Full | Best support |
| Firefox | ✅ Full | Fully supported |
| Safari | ⚠️ Partial | Audio playback works, recording may need permissions |
| Edge | ✅ Full | Good support |

## Troubleshooting

### No audio being captured
1. Check browser permissions: Settings → Privacy → Microphone
2. Ensure microphone is not muted
3. Try a different browser tab

### Jimmy not responding
1. Check network console for errors
2. Verify patient is logged in
3. Check Flask server logs

### Audio response not playing
1. Check browser volume settings
2. Ensure audio context is not suspended
3. Check CORS settings

### VAD not detecting end of speech
1. Increase silenceDuration (default 1000ms)
2. Ensure consistent background noise level
3. Speak more slowly with clear pauses

## Deployment Checklist

- [x] webrtcvad installed
- [x] edge_tts or gTTS available
- [x] Flask app running on port 5000
- [x] Session/authentication working
- [x] Meralion API key configured
- [x] Groq API key configured
- [x] HTTPS recommended for production (browser mic requires secure context in some cases)

## Support

For issues or questions:
1. Check Flask server logs for backend errors
2. Check browser console for frontend errors
3. Verify all API keys are configured correctly
4. Test individual components (transcription, TTS) separately
