#!/usr/bin/env python3
"""Test Meralion API connectivity."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from merilion_client import test_connection, MERILION_API_KEY, MERILION_BASE_URL

print("=" * 60)
print("MERALION API TEST")
print("=" * 60)
print(f"\n✓ Base URL: {MERILION_BASE_URL}")
print(f"✓ API Key loaded: {bool(MERILION_API_KEY)}")
print(f"✓ API Key length: {len(MERILION_API_KEY) if MERILION_API_KEY else 0}")
print(f"✓ API Key first 5 chars: {MERILION_API_KEY[:5] if MERILION_API_KEY else 'MISSING'}...")

print("\n" + "=" * 60)
print("Testing chat endpoint...")
print("=" * 60)

result = test_connection()
print(f"\nResult: {result}")

if result.get("ok"):
    print("\n✅ SUCCESS: Meralion API is working!")
else:
    print(f"\n❌ FAILED: {result.get('error') or result}")
