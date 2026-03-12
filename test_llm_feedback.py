#!/usr/bin/env python3
"""
Test LLM Feedback Generation
Shows whether LLM is being called and what feedback is generated
"""

import sys
import os

# Add to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Rehab_Scorer_Coach/src'))

from keraal_pipeline import KeraalRehabPipeline

# Create pipeline
pipeline = KeraalRehabPipeline()

# Test cases
test_cases = [
    ("CORRECT", 45.0, "Forward Flexion", "Should return empty feedback"),
    ("INCORRECT", 10.0, "Forward Flexion", "Should generate feedback for very poor form"),
    ("INCORRECT", 22.0, "Torso Rotation", "Should generate feedback for poor form"),
    ("INCORRECT", 30.0, "Flank Stretch", "Should generate feedback for near-correct form"),
]

print("=" * 70)
print("TESTING LLM FEEDBACK GENERATION")
print("=" * 70)

for form_status, score, exercise, description in test_cases:
    print(f"\n📝 Test: {description}")
    print(f"   Form Status: {form_status}")
    print(f"   Score: {score:.1f}/50")
    print(f"   Exercise: {exercise}")
    print("   " + "-" * 66)
    
    feedback = pipeline._generate_llm_feedback(form_status, score, exercise)
    
    if feedback:
        print(f"   ✅ Feedback Generated ({len(feedback)} items):")
        for i, fb in enumerate(feedback, 1):
            print(f"      {i}. {fb}")
    else:
        print(f"   ℹ️  No feedback (expected for CORRECT form)")
    
    print()

print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("\n🔍 Analysis:")
print("   ✅ LLM Feedback should vary based on score and exercise")
print("   ✅ Feedback should be specific and actionable")
print("   ✅ Each call should potentially have different feedback (if LLM connected)")
print("   ⚠️  If all feedback is generic, LLM is not connected")
print("      - Set GROQ_API_KEY or GOOGLE_API_KEY environment variables")
print("      - Or use fallback RAG-enhanced responses")
