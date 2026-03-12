#!/usr/bin/env python3
"""
Test Meralion API key validity and query parameter authentication
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
print("MERALION API KEY VALIDATION")
print("=" * 70)
print(f"API Key: {meralion_api_key}")
print(f"Length: {len(meralion_api_key)} chars")

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

# Test 1: Query parameter
print("\n1️⃣ Testing query parameter (api_key=...):")
try:
    response = requests.post(
        f"{base_url}/process/transcribe?api_key={meralion_api_key}",
        files=files,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code < 400:
        print(f"   ✅ SUCCESS")
    else:
        try:
            print(f"   Error: {response.json()['status']['message']}")
        except:
            print(f"   Error: {response.text[:100]}")
except Exception as e:
    print(f"   Exception: {e}")

# Test 2: Key query parameter (different name)
print("\n2️⃣ Testing query parameter (key=...):")
try:
    response = requests.post(
        f"{base_url}/process/transcribe?key={meralion_api_key}",
        files=files,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code < 400:
        print(f"   ✅ SUCCESS")
    else:
        try:
            print(f"   Error: {response.json()['status']['message']}")
        except:
            print(f"   Error: {response.text[:100]}")
except Exception as e:
    print(f"   Exception: {e}")

# Test 3: Check if endpoint even exists with simple test
print("\n3️⃣ Testing chat endpoint (known to work):")
try:
    response = requests.post(
        f"{base_url}/chat",
        json={"instruction": "Say 'test'", "question": "answer"},
        headers={"x-api-key": meralion_api_key},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ SUCCESS - Chat endpoint works with x-api-key")
        print(f"   Response: {str(response.json())[:100]}")
    else:
        print(f"   Error: {response.status_code} - {response.text[:100]}")
except Exception as e:
    print(f"   Exception: {e}")

# Test 4: Try with only Content-Type
print("\n4️⃣ Testing with minimal headers (x-api-key only, no Accept):")
try:
    response = requests.post(
        f"{base_url}/process/transcribe",
        files=files,
        headers={"x-api-key": meralion_api_key},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code < 400:
        print(f"   ✅ SUCCESS")
        print(f"   Response: {response.text[:150]}")
    else:
        try:
            print(f"   Error: {response.json()['status']['message']}")
        except:
            print(f"   Error: {response.text[:100]}")
except Exception as e:
    print(f"   Exception: {e}")

print("\n" + "=" * 70)
print("DIAGNOSIS: Check if the API key format is correct")
print("=" * 70)
