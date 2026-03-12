#!/usr/bin/env python3
"""
Debug script to test pipeline initialization and feedback generation directly.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env from {env_path}")
else:
    print(f"❌ .env not found at {env_path}")

print("\n" + "="*80)
print("ENVIRONMENT CHECK")
print("="*80)
print(f"GROQ_API_KEY: {os.getenv('GROQ_API_KEY', 'NOT SET')[:20]}...")
print(f"MERILION_API_KEY: {os.getenv('MERILION_API_KEY', 'NOT SET')[:20]}...")

# Test 1: Direct Groq Test
print("\n" + "="*80)
print("TEST 1: DIRECT GROQ CLIENT")
print("="*80)
try:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Say 'test ok'"}],
        max_tokens=10
    )
    print(f"✅ Groq client works: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Groq client failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: GroqLLM class
print("\n" + "="*80)
print("TEST 2: GroqLLM CLASS INITIALIZATION")
print("="*80)
try:
    from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
    llm = GroqLLM()
    print(f"✅ GroqLLM initialized successfully")
    print(f"   Model: {llm.model}")
    print(f"   API Key: {llm.api_key[:20]}...")
except Exception as e:
    print(f"❌ GroqLLM initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: LLM Feedback generation
print("\n" + "="*80)
print("TEST 3: LLM FEEDBACK GENERATION")
print("="*80)
try:
    feedback = llm.generate_feedback(
        exercise_name="squat",
        language="English",
        rag_context="Keep knees aligned with toes",
        numeric_summary="Score: 45/50",
        pose_summary="Knees slightly inward, back upright"
    )
    print(f"✅ Feedback generated successfully:")
    for i, item in enumerate(feedback, 1):
        print(f"   {i}. {item}")
except Exception as e:
    print(f"❌ Feedback generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: WebRehabPipeline
print("\n" + "="*80)
print("TEST 4: WEBREHAB PIPELINE INITIALIZATION")
print("="*80)
try:
    from Rehab_Scorer_Coach.src.web_pipeline import WebRehabPipeline
    pipeline = WebRehabPipeline()
    print(f"✅ WebRehabPipeline initialized successfully")
    print(f"   LLM: {pipeline.llm}")
    print(f"   RAG: {pipeline.rag}")
except Exception as e:
    print(f"❌ WebRehabPipeline initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: KeraalRehabPipeline
print("\n" + "="*80)
print("TEST 5: KERAAL REHAB PIPELINE INITIALIZATION")
print("="*80)
try:
    from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
    pipeline = KeraalRehabPipeline()
    print(f"✅ KeraalRehabPipeline initialized successfully")
    print(f"   LLM: {pipeline.llm}")
    print(f"   RAG: {pipeline.rag}")
except Exception as e:
    print(f"❌ KeraalRehabPipeline initialization failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: Flask app startup
print("\n" + "="*80)
print("TEST 6: FLASK APP STARTUP")
print("="*80)
try:
    import main
    print(f"✅ Flask app imported successfully")
except Exception as e:
    print(f"❌ Flask app import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
print("✅ ALL TESTS PASSED - SYSTEM IS WORKING")
print("="*80)
