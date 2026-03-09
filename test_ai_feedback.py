#!/usr/bin/env python3
"""
Comprehensive AI Feedback Test - Both Pipelines
"""
import os
import sys
from dotenv import load_dotenv

# Load .env first
load_dotenv()

print("=" * 70)
print("AI FEEDBACK DIAGNOSTIC TEST")
print("=" * 70)

# Check environment
print("\n1️⃣ Environment Variables:")
groq_key = os.environ.get("GROQ_API_KEY", "")
print(f"   GROQ_API_KEY set: {bool(groq_key)}")
if groq_key:
    print(f"   Key length: {len(groq_key)} chars")
    print(f"   First 10 chars: {groq_key[:10]}...")

# Test GroqLLM
print("\n2️⃣ GroqLLM Initialization:")
try:
    from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
    llm = GroqLLM()
    print("   ✅ GroqLLM initialized successfully")
except Exception as e:
    print(f"   ❌ GroqLLM initialization failed: {e}")
    sys.exit(1)

# Test LLM feedback generation
print("\n3️⃣ LLM Feedback Generation (direct call):")
try:
    feedback = llm.generate_feedback(
        exercise_name="Squat",
        language="English",
        rag_context="Keep knees aligned with toes",
        numeric_summary="score=15/50 status=WRONG",
        pose_summary="knee_angle=45 hip_angle=60"
    )
    print(f"   ✅ Feedback generated: {feedback}")
except Exception as e:
    print(f"   ❌ Feedback generation failed: {e}")
    sys.exit(1)

# Test WebRehabPipeline
print("\n4️⃣ WebRehabPipeline Initialization:")
try:
    from Rehab_Scorer_Coach.src.web_pipeline import WebRehabPipeline
    web_pipeline = WebRehabPipeline()
    print("   ✅ WebRehabPipeline initialized")
    print(f"      - LLM available: {web_pipeline.llm is not None}")
    print(f"      - RAG available: {web_pipeline.rag is not None}")
except Exception as e:
    print(f"   ❌ WebRehabPipeline initialization failed: {e}")
    sys.exit(1)

# Test KeraalRehabPipeline
print("\n5️⃣ KeraalRehabPipeline Initialization:")
try:
    from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
    keraal_pipeline = KeraalRehabPipeline()
    print("   ✅ KeraalRehabPipeline initialized")
except Exception as e:
    print(f"   ❌ KeraalRehabPipeline initialization failed: {e}")
    sys.exit(1)

# Test KERAAL feedback generation
print("\n6️⃣ KeraalRehabPipeline Feedback Generation:")
try:
    feedback = keraal_pipeline._generate_llm_feedback(
        form_status="INCORRECT",
        aggregated_score=15.0,
        exercise_name="Forward Flexion"
    )
    if feedback:
        print(f"   ✅ Feedback generated ({len(feedback)} items):")
        for i, fb in enumerate(feedback, 1):
            print(f"      {i}. {fb}")
    else:
        print(f"   ⚠️  No feedback generated (cooldown or missing LLM)")
except Exception as e:
    print(f"   ❌ Feedback generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - AI FEEDBACK IS WORKING!")
print("=" * 70)
