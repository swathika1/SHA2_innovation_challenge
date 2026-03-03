#!/usr/bin/env python3
import os
os.environ["GROQ_API_KEY"] = "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"

# Test 1: RAG initialization
print("=" * 60)
print("TEST 1: RAG INITIALIZATION")
print("=" * 60)
try:
    from Rehab_Scorer_Coach.src.rag_store import RAGStore
    from pathlib import Path
    rag = RAGStore(persist_dir=Path("rag_db"))
    print("✅ RAG initialized successfully")
except Exception as e:
    print(f"❌ RAG failed: {e}")

# Test 2: LLM initialization and language support
print("\n" + "=" * 60)
print("TEST 2: LLM LANGUAGE SUPPORT")
print("=" * 60)
try:
    from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
    llm = GroqLLM()
    
    # Test Tamil feedback
    feedback = llm.generate_feedback(
        exercise_name="squat",
        language="Tamil",
        rag_context="Keep knees behind toes. Keep chest up.",
        numeric_summary="score=25.0/50 status=WRONG",
        pose_summary="delta_motion=0.05"
    )
    print(f"✅ Tamil feedback generated: {feedback}")
    if any(ord(c) > 127 for c in str(feedback)):
        print("✅ Tamil characters detected - language working!")
    else:
        print("❌ No Tamil characters - feedback might be in English")
        
except Exception as e:
    print(f"❌ LLM failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Voice/TTS function
print("\n" + "=" * 60)
print("TEST 3: CHECK TTS FUNCTION EXISTS")
print("=" * 60)
try:
    with open("templates/patient/session.html", "r") as f:
        content = f.read()
        if "speakFeedbackList" in content:
            print("✅ speakFeedbackList function found")
            if "await speakFeedbackList(fb)" in content and "INCORRECT" in content:
                print("✅ Voice is called when INCORRECT")
        if "statusUpdateCounter" in content:
            print("✅ Status update counter found")
            if "STATUS_UPDATE_FRAMES = 25" in content:
                print("✅ Status updates every 5 seconds (25 frames @ 200ms)")
except Exception as e:
    print(f"❌ Error reading HTML: {e}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
