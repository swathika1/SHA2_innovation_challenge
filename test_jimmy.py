#!/usr/bin/env python3
"""Test Jimmy avatar functionality"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent / ".env")
print("✅ Loaded .env")

# Test 1: Import test
print("\n" + "="*80)
print("TEST 1: IMPORT MERALION_AVATAR")
print("="*80)
try:
    from meralion_avatar import get_avatar, AvatarJimmy
    print("✅ Successfully imported meralion_avatar module")
    avatar = get_avatar()
    print(f"✅ Got avatar instance: {avatar}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 2: Query Jimmy
print("\n" + "="*80)
print("TEST 2: QUERY JIMMY (WITHOUT DATABASE)")
print("="*80)
try:
    # Test with a simple query (doesn't need database patched)
    response = avatar.query_jimmy(
        patient_id=99999,  # Dummy ID
        user_message="Hello Jimmy, how are you?",
        conversation_history=[],
        include_rag=False,  # Skip RAG to avoid any DB issues
        include_performance=False,  # Skip performance to avoid DB issues
        preferred_language="English"
    )
    print(f"✅ Got response from Jimmy:")
    print(f"   {response[:100]}...")
except Exception as e:
    print(f"❌ Query failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "="*80)
print("✅ JIMMY AVATAR WORKING")
print("="*80)
