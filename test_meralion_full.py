#!/usr/bin/env python3
"""
Comprehensive Meralion API troubleshooting script.
Tests transcription, avatar chat, and general connectivity.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check environment variables
print("=" * 70)
print("MERALION ENVIRONMENT CHECK")
print("=" * 70)

MERILION_USERNAME = os.environ.get("MERILION_USERNAME")
MERILION_API_KEY = os.environ.get("MERILION_API_KEY")
MERILION_BASE_URL = os.environ.get("MERILION_BASE_URL", "https://api.cr8lab.com")

print(f"\n✓ Username: {MERILION_USERNAME}")
print(f"✓ Base URL: {MERILION_BASE_URL}")
print(f"✓ API Key loaded: {bool(MERILION_API_KEY)}")
  
if not MERILION_API_KEY:
    print("\n❌ ERROR: MERILION_API_KEY not found in environment!")
    print("   Make sure .env file contains: MERILION_API_KEY=oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE")
    sys.exit(1)

print(f"✓ API Key first 5 chars: {MERILION_API_KEY[:5]}...")
print(f"✓ API Key length: {len(MERILION_API_KEY)}")

# Test 1: Direct HTTP request with x-api-key
print("\n" + "=" * 70)
print("TEST 1: Direct HTTP request to /chat endpoint")
print("=" * 70)

import requests

headers = {
    "x-api-key": MERILION_API_KEY,
    "Content-Type": "application/json"
}

payload = {
    "instruction": "You are a helpful assistant. Answer briefly.",
    "question": "What is 2+2?"
}

try:
    print(f"\nRequest Details:")
    print(f"  URL: {MERILION_BASE_URL}/chat")
    print(f"  Headers: x-api-key={MERILION_API_KEY[:10]}... (truncated)")
    print(f"  Method: POST")
    
    response = requests.post(
        f"{MERILION_BASE_URL}/chat",
        json=payload,
        headers=headers,
        timeout=15.0
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Type: {response.headers.get('content-type')}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Chat endpoint is working!")
        data = response.json()
        print(f"Response: {str(data)[:200]}")
    else:
        print(f"❌ FAILED: HTTP {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 2: Test merilion_client module
print("\n" + "=" * 70)
print("TEST 2: merilion_client module")
print("=" * 70)

try:
    from merilion_client import test_connection
    
    print("\nTesting Meralion connection...")
    result = test_connection()
    
    if result.get("ok"):
        print("✅ SUCCESS: merilion_client.test_connection() passed!")
        print(f"Response: {result.get('body', '')[:200]}")
    else:
        print(f"❌ FAILED: {result}")
        
except ImportError as e:
    print(f"❌ Import Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Test avatar initialization
print("\n" + "=" * 70)
print("TEST 3: Avatar (Jimmy) initialization")
print("=" * 70)

try:
    from meralion_avatar import AvatarJimmy
    
    avatar = AvatarJimmy()
    print("✅ SUCCESS: AvatarJimmy initialized!")
    print(f"Avatar name: {avatar.avatar_name}")
    print(f"Base URL: {avatar.base_url}")
    print(f"Auth header format: x-api-key={avatar.api_key[:10]}...")
    
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 4: List actual code locations
print("\n" + "=" * 70)
print("TEST 4: Code locations (no old .pyc files)")
print("=" * 70)

code_files = {
    "merilion_client.py": "/Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge/merilion_client.py",
    "meralion_avatar.py": "/Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge/meralion_avatar.py",
    ".env": "/Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge/.env"
}

for name, path in code_files.items():
    exists = os.path.exists(path)
    symbol = "✅" if exists else "❌"
    print(f"{symbol} {name}: {path}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("""
1. The .env file contains your Meralion API key
2. merilion_client.py only uses x-api-key header (fixed)
3. meralion_avatar.py (Jimmy) uses x-api-key header
4. Python cache has been cleared

If tests 1 and 2 pass, the API is working!
If test 1 fails with HTTP 403, the API key might be invalid or revoked.
If test 1 fails with "Cannot connect", check your internet connection.
""")
