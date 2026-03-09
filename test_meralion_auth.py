#!/usr/bin/env python3
"""
Test different Meralion authentication methods
"""
import os
import requests
import wave
import io
from dotenv import load_dotenv

load_dotenv()

meralion_api_key = os.environ.get("MERILION_API_KEY", "")
base_url = os.environ.get("MERILION_BASE_URL", "https://api.cr8lab.com")

print("=" * 70)
print("MERALION AUTHENTICATION TEST")
print("=" * 70)
print(f"API Key: {meralion_api_key[:10]}... ({len(meralion_api_key)} chars)")
print(f"Base URL: {base_url}")

# Create dummy audio
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
files = {"file": ("test.wav", audio_bytes, "audio/wav")}

# Test different authentication methods
tests = [
    ("x-api-key header", {"x-api-key": meralion_api_key}),
    ("X-API-Key header (uppercase)", {"X-API-Key": meralion_api_key}),
    ("api-key header", {"api-key": meralion_api_key}),
    ("Authorization Bearer", {"Authorization": f"Bearer {meralion_api_key}"}),
    ("Authorization ApiKey", {"Authorization": f"ApiKey {meralion_api_key}"}),
]

urls = [
    f"{base_url}/process/transcribe",
    f"{base_url}/transcribe",
]

print("\nTesting endpoints and authentication methods:")
print("-" * 70)

for url in urls:
    print(f"\n🔗 URL: {url}")
    for test_name, headers in tests:
        try:
            # Add common headers
            full_headers = {**headers, "Accept": "application/json"}
            
            response = requests.post(
                url,
                files=files,
                headers=full_headers,
                timeout=10
            )
            
            status = "✅" if response.status_code < 400 else "❌"
            print(f"  {status} {test_name}: HTTP {response.status_code}")
            
            if response.status_code >= 400:
                # Show first 100 chars of error
                try:
                    error_text = response.json()
                    msg = error_text.get("status", {}).get("message", str(error_text))[:80]
                except:
                    msg = response.text[:80]
                print(f"      → {msg}")
            else:
                print(f"      ✅ SUCCESS!")
                print(f"         Response: {str(response.json())[:150]}")
        except Exception as e:
            print(f"  ❌ {test_name}: {str(e)[:80]}")

print("\n" + "=" * 70)
