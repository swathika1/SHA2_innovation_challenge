import requests
import httpx
from config import MERILION_USERNAME, MERILION_API_KEY, MERILION_BASE_URL

SAFETY_RULES = """Rules:
- NEVER provide a medical diagnosis
- If asked to diagnose, say: "I'm not able to diagnose conditions. Please consult your doctor."
- Be empathetic, clear, and concise
- Respond in the same language the patient uses (English, 中文, Bahasa Melayu, தமிழ்)"""

APP_CONTEXT = """
=== APP DATABASE SCHEMA (rehab_coach.db — SQLite) ===
You have access to patient data from these tables. Use this to give informed, personalized answers.

1. users — id, email, name, role (doctor/patient/caregiver), phone, created_at
2. patients — user_id, condition, surgery_date, current_week, adherence_rate (%), avg_pain_level (0-10), avg_quality_score (0-100), completed_sessions, streak_days
3. doctor_patient — doctor_id, patient_id, assigned_date
4. caregiver_patient — caregiver_id, patient_id, relationship
5. exercises — id, name, description, category, difficulty (1-5), video_url
6. workouts — patient_id, exercise_id, sets, reps, frequency, instructions, is_active
7. sessions — patient_id, started_at, completed_at, pain_before (0-10), pain_after (0-10), effort_level, quality_score (0-100), completed_perc (%)
8. session_exercises — session_id, workout_id, exercise_name, quality_score, sets_required/completed (JSON)
9. session_frames — frame-level telemetry: session_id, exercise_name, score, status, rep_count, set_count
10. appointments — doctor_id, patient_id, date, time, duration, status (scheduled/completed/cancelled)
11. clinician_notes — doctor notes about patients
12. caregiver_requests — caregiver access requests (pending/approved/rejected)
13. login_history — user login audit trail

=== RAG KNOWLEDGE BASES ===
Two vector stores provide exercise guidance that may be injected as context:

FAISS (vector_store/) — Keraal PDF guides, rehabilitation literature
ChromaDB (rag_db/) — Comprehensive exercise knowledge:

KIMORE Exercises (motion-capture scoring, 0-50 scale):
  1. Lifting of Arms — shoulder mobility, lateral arm raise
  2. Lateral Trunk Tilt — trunk lateral flexibility
  3. Trunk Rotation — spinal rotational mobility
  4. Squat — lower limb strength, hip/knee flexion
  5. Trunk Rotation & Target — rotation + reaching coordination
  Scoring: Primary Outcome (0-15) + Control Factor (0-35) = 0-50

KERAAL Exercises (webcam BlazePose scoring, 0-50 scale):
  - Forward Flexion (CTK) — hip hinge, hamstring stretch
  - Flank Stretch (ELK) — lateral trunk stretch
  - Torso Rotation (RTK) — trunk rotation
  Scoring: ≥27.5/50 = CORRECT form

General: Safety guidelines, scoring systems, LBP rehab protocols

=== APP FEATURES ===
- Real-time webcam exercise scoring (OpenPose/BlazePose skeleton detection)
- Pain tracking before/after sessions (0-10)
- Quality scoring per session (0-100)
- Adherence rate and streak tracking
- Doctor dashboard, caregiver access workflow
- Appointment scheduling with optimization
- Multilingual: English, Chinese, Malay, Tamil, Singlish
- Avatar coach (Jimmy) for voice/text interaction
"""


def _build_headers() -> dict:
    """Build auth headers for MERaLiON API."""
    return {
        "x-api-key": MERILION_API_KEY,
        "Content-Type": "application/json"
    }


LANGUAGE_INSTRUCTIONS = {
    "ms": "PENTING: Pesakit menulis dalam Bahasa Melayu. Anda MESTI membalas SEPENUHNYA dalam Bahasa Melayu. Jangan gunakan bahasa Inggeris langsung.",
    "zh": "重要：患者用中文书写。您必须完全用中文回复。请勿使用英语。",
    "ta": "முக்கியம்: நோயாளி தமிழில் எழுதுகிறார். நீங்கள் முழுவதுமாக தமிழில் பதிலளிக்க வேண்டும். ஆங்கிலம் பயன்படுத்த வேண்டாம்.",
    "en": ""
}


def _build_chat_payload(messages: list, patient_context: str, rag_context: str = "", lang_key: str = "en") -> dict:
    # sourcery skip: merge-list-appends-into-extend, use-named-expression
    """Build payload for MERaLiON /chat endpoint.

    MERaLiON responds best when the full prompt is in the 'instruction' field.
    We compose instruction = patient context + conversation history + user question + safety rules.
    """
    # Extract the latest user message and conversation history
    question = ""
    history_lines = []

    for msg in messages:
        if msg["role"] == "user":
            question = msg["content"]
        elif msg["role"] == "assistant":
            history_lines.append(f"Assistant: {msg['content']}")
        elif msg["role"] == "system":
            history_lines.append(f"[Note: {msg['content']}]")

    # Build the full instruction that MERaLiON will respond to
    instruction_parts = [
        "You are a healthcare rehab assistant for the Home Rehab Coach app. Answer the patient's question directly with specific, practical advice.",
        SAFETY_RULES,
        APP_CONTEXT
    ]

    # Explicit language override — placed early so the model sees it clearly
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang_key, "")
    if lang_instruction:
        instruction_parts.append(f"\n{lang_instruction}")

    if patient_context and patient_context != "New patient - no history available.":
        instruction_parts.append(f"\nPatient Info:\n{patient_context}")

    if history_lines:
        instruction_parts.append("\nPrevious conversation:\n" + "\n".join(history_lines[-6:]))

    # RAG context — inject rehabilitation knowledge if available
    if rag_context and rag_context.strip():
        instruction_parts.append(f"\nRelevant Rehabilitation Knowledge (use this to inform your answer):\n{rag_context}")

    instruction_parts.append(f"\nPatient asks: {question}")
    instruction_parts.append("\nRespond directly to their question with helpful, specific advice. Reference the rehabilitation knowledge above when relevant:")

    return {
        "instruction": "\n".join(instruction_parts),
        "question": "answer"
    }


def _extract_response(data: dict) -> str:
    """Extract text from MERaLiON API response."""
    if "response" in data and isinstance(data["response"], dict):
        return data["response"].get("text", str(data["response"]))
    elif "response" in data:
        return str(data["response"])
    elif "choices" in data:
        return data["choices"][0]["message"]["content"]
    else:
        return str(data)


def query_merilion_sync(messages: list, patient_context: str, rag_context: str = "", lang_key: str = "en") -> str:
    """Synchronous version for Flask routes."""
    headers = _build_headers()
    payload = _build_chat_payload(messages, patient_context, rag_context, lang_key)

    response = requests.post(
        f"{MERILION_BASE_URL}/chat",
        json=payload,
        headers=headers,
        timeout=30.0
    )
    response.raise_for_status()
    return _extract_response(response.json())


async def query_merilion(messages: list, patient_context: str, rag_context: str = "", lang_key: str = "en") -> str:
    """Async version for FastAPI routes."""
    headers = _build_headers()
    payload = _build_chat_payload(messages, patient_context, rag_context, lang_key)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MERILION_BASE_URL}/chat",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        return _extract_response(response.json())


def translate_text_sync(text: str, target_language: str) -> str:
    """Translate text to target_language using MERaLiON."""
    lang_full = {
        "Chinese": "Chinese (Simplified)",
        "Malay": "Bahasa Melayu",
        "Tamil": "Tamil",
        "English": "English"
    }
    target = lang_full.get(target_language, target_language)
    headers = _build_headers()
    payload = {
        "instruction": f"Translate the following text to {target}. Output ONLY the translated text, no explanations, no preamble:\n\n{text}",
        "question": "answer"
    }
    r = requests.post(f"{MERILION_BASE_URL}/chat", json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    return _extract_response(r.json())


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm", vocab_hint: str = "") -> str:
    """Transcribe audio using MERaLiON /process/transcribe endpoint.
    
    Falls back to whisper_transcriber if Meralion transcription fails.
    """
    # Use correct MIME type based on filename extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    mime_map = {"webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4",
                "wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4"}
    content_type = mime_map.get(ext, "audio/webm")

    files = {"file": (filename, audio_bytes, content_type)}
    form_data = {}
    if vocab_hint:
        form_data["prompt"] = vocab_hint

    print(f"[TRANSCRIBE] Sending {len(audio_bytes)} bytes ({content_type}) to Meralion")

    api_key = (MERILION_API_KEY or "").strip()
    
    base = (MERILION_BASE_URL or "").rstrip("/")
    url_candidates = [
        f"{base}/process/transcribe",
        f"{base}/transcribe",
    ]
    header_candidates = [
        {"x-api-key": api_key, "Accept": "application/json"},
    ]

    errors = []
    data = None
    for url in url_candidates:
        for headers in header_candidates:
            try:
                r = requests.post(
                    url,
                    files=files,
                    data=form_data if form_data else None,
                    headers=headers,
                    timeout=30
                )
                print(f"[TRANSCRIBE] URL={url} status={r.status_code}")
                if r.status_code >= 400:
                    body_preview = (r.text or "")[:150]
                    errors.append(f"{url} [HTTP {r.status_code}]")
                    continue

                try:
                    data = r.json()
                    print(f"[TRANSCRIBE] ✅ Success: {data}")
                except Exception:
                    body_preview = (r.text or "")[:150]
                    errors.append(f"Non-JSON response")
                    continue

                break
            except Exception as e:
                errors.append(f"{url} exception: {str(e)[:50]}")
                continue
        if data is not None:
            break

    # Fallback: Use Whisper/Groq transcription if Meralion fails
    if data is None:
        print(f"[TRANSCRIBE] ⚠️  Meralion transcribe failed ({len(errors)} errors), trying Whisper fallback...")
        try:
            # Try Whisper via Groq or other transcription service
            try:
                from whisper_transcriber import transcribe as whisper_transcribe
                print(f"[TRANSCRIBE] Using Whisper fallback")
                transcript = whisper_transcribe(audio_bytes, filename)
                if transcript:
                    return transcript
            except Exception as whisper_err:
                print(f"[TRANSCRIBE] Whisper also failed: {whisper_err}")
            
            # Final fallback: Return empty string instead of crashing
            print(f"[TRANSCRIBE] All transcription methods failed, returning empty string")
            return ""
        except Exception as fallback_err:
            print(f"[TRANSCRIBE] Error in fallback: {fallback_err}")
            return ""

    # Parse response from Meralion
    transcript = (
        data.get("transcript") or
        data.get("text") or
        data.get("transcription") or
        data.get("output") or
        ""
    )
    return transcript if isinstance(transcript, str) else str(transcript)


def test_connection() -> dict:
    """Test connectivity to MERaLiON API with a real chat call."""
    headers = _build_headers()
    try:
        response = requests.post(
            f"{MERILION_BASE_URL}/chat",
            json={
                "instruction": "A patient in ACL rehab week 1 asks: My knee hurts during wall squats. What should I do instead? Give 2 alternatives.",
                "question": "answer"
            },
            headers=headers,
            timeout=15.0
        )
        return {
            "ok": response.status_code == 200,
            "status_code": response.status_code,
            "body": response.json().get("response", {}).get("text", response.text[:300])
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print(f"Testing connection to {MERILION_BASE_URL}...")
    result = test_connection()
    print(f"Status: {result}")
