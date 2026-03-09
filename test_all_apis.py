#!/usr/bin/env python3
"""
Test transcription and AI feedback with new API keys
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("API KEY VALIDATION")
print("=" * 70)

groq_key = os.environ.get("GROQ_API_KEY", "")
meralion_key = os.environ.get("MERILION_API_KEY", "")

print(f"\n✓ GROQ_API_KEY: {groq_key[:20]}... ({len(groq_key)} chars)")
print(f"✓ MERILION_API_KEY: {meralion_key[:20]}... ({len(meralion_key)} chars)")

# Test 1: Groq LLM
print("\n" + "=" * 70)
print("TEST 1: GROQ LLM DIRECT")
print("=" * 70)

try:
    from groq import Groq
    client = Groq(api_key=groq_key)
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say 'Test OK' only."}
        ],
        max_tokens=50
    )
    
    print(f"✅ Groq API working!")
    print(f"   Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Groq API failed: {e}")

# Test 2: GroqLLM wrapper
print("\n" + "=" * 70)
print("TEST 2: GroqLLM WRAPPER")
print("=" * 70)

try:
    from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
    llm = GroqLLM()
    
    feedback = llm.generate_feedback(
        exercise_name="Squat",
        language="English",
        rag_context="Keep knees aligned",
        numeric_summary="score=20/50",
        pose_summary="poor alignment"
    )
    print(f"✅ GroqLLM wrapper working!")
    print(f"   Feedback: {feedback}")
except Exception as e:
    print(f"❌ GroqLLM wrapper failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Meralion transcription
print("\n" + "=" * 70)
print("TEST 3: MERALION TRANSCRIPTION CHECK")
print("=" * 70)

try:
    import requests
    
    # Create a dummy WAV file for testing
    import wave
    import io
    
    # Create 1-second of silence at 16kHz
    sample_rate = 16000
    duration_sec = 1
    num_samples = sample_rate * duration_sec
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00' * (num_samples * 2))
    
    audio_bytes = wav_buffer.getvalue()
    
    headers = {
        "x-api-key": meralion_key,
        "Accept": "application/json"
    }
    
    files = {"file": ("test.wav", audio_bytes, "audio/wav")}
    
    response = requests.post(
        "https://api.cr8lab.com/process/transcribe",
        files=files,
        headers=headers,
        timeout=15
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code == 200:
        print("✅ Meralion transcription endpoint working!")
    else:
        print(f"❌ Meralion returned {response.status_code}: {response.text[:300]}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
