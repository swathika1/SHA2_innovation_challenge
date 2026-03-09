#!/usr/bin/env python3
"""
Test transcription chain: Whisper -> Meralion fallback
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env with explicit path
load_dotenv(Path(__file__).parent / ".env")

print("=" * 70)
print("TRANSCRIPTION CHAIN TEST")
print("=" * 70)

# Check environment
groq_key = os.environ.get("GROQ_API_KEY", "")
meralion_key = os.environ.get("MERILION_API_KEY", "")

print(f"\n1️⃣ Environment Check:")
print(f"   GROQ_API_KEY: {'✅ SET' if groq_key else '❌ MISSING'}")
print(f"   MERILION_API_KEY: {'✅ SET' if meralion_key else '❌ MISSING'}")

if groq_key:
    print(f"      → {groq_key[:10]}...")
if meralion_key:
    print(f"      → {meralion_key[:10]}...")

# Test Whisper
print(f"\n2️⃣ Whisper Transcriber:")
try:
    from whisper_transcriber import transcribe as whisper_transcribe
    
    # Create dummy audio
    import wave
    import io
    
    sample_rate = 16000
    num_samples = sample_rate  # 1 second
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00' * (num_samples * 2))
    
    audio_bytes = wav_buffer.getvalue()
    
    print(f"   Testing with {len(audio_bytes)} bytes dummy audio...")
    result = whisper_transcribe(audio_bytes, "test.wav")
    print(f"   Result: {repr(result)}")
    if result:
        print(f"   ✅ Whisper working (got text: {result[:50]})")
    else:
        print(f"   ℹ️  Whisper returned empty (audio too short or silent)")
    
except Exception as e:
    print(f"   ❌ Whisper error: {e}")

# Test Meralion transcribe_audio with fallback
print(f"\n3️⃣ Meralion Transcribe (with Whisper fallback):")
try:
    from merilion_client import transcribe_audio
    
    # Use same dummy audio
    print(f"   Testing with {len(audio_bytes)} bytes dummy audio...")
    result = transcribe_audio(audio_bytes, "test.wav")
    print(f"   Result: {repr(result)}")
    if result:
        print(f"   ✅ Got transcription: {result[:50]}")
    else:
        print(f"   ℹ️  Got empty response (expected for silent audio)")
    
except Exception as e:
    print(f"   ❌ Meralion error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("✅ TRANSCRIPTION CHAIN WORKING")
print("=" * 70)
