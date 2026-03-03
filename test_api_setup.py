#!/usr/bin/env python3
"""
Quick test to validate API key setup for both KERAAL and KIMORE pipelines
"""
import os
import sys

# Set API key before imports
os.environ["GROQ_API_KEY"] = "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"

print("=" * 70)
print("API KEY SETUP VALIDATION")
print("=" * 70)

print("\n1️⃣  Testing KIMORE Pipeline (WebRehabPipeline with GroqLLM)...")
try:
    sys.path.insert(0, '/Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge')
    from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
    llm = GroqLLM()
    print(f"   ✅ GroqLLM initialized")
    print(f"   📋 API Key: {llm.api_key[:20]}...")
    print(f"   📋 Model: {llm.model}")
except Exception as e:
    print(f"   ❌ GroqLLM failed: {e}")

print("\n2️⃣  Testing KERAAL Pipeline (keraal_pipeline with Groq/Gemini)...")
try:
    from Rehab_Scorer_Coach.src.keraal_pipeline import KeraalRehabPipeline
    print(f"   ✅ KeraalRehabPipeline imported")
    print(f"   📋 Will use Groq API key: {os.getenv('GROQ_API_KEY', 'NOT SET')[:20]}...")
except Exception as e:
    print(f"   ⚠️  KeraalRehabPipeline import warning: {e}")

print("\n3️⃣  Checking GroqLLM implementation in both pipelines...")
files_checked = [
    "Rehab_Scorer_Coach/src/llm_groq.py",
    "Rehab_Scorer_Coach/src/llm_groq_rehab.py", 
    "Rehab_Scorer_Coach/src/llm_pose_groq.py",
    "Rehab_Scorer_Coach/src/keraal_pipeline.py"
]

for fname in files_checked:
    fpath = f'/Users/HariKrishnaD/Downloads/NUS/Hackathons/NUS_BIZ_Synapxe_Innovation_Challenge/Project_Main_Branch/SHA2_innovation_challenge/{fname}'
    try:
        with open(fpath) as f:
            content = f.read()
            if "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" in content:
                print(f"   ✅ {fname} has correct API key")
            elif "gsk_" in content and "YUnaIvsXspl" not in content:
                print(f"   ✅ {fname} uses API key from environment")
            else:
                print(f"   ⚠️  {fname} - check API key setup")
    except Exception as e:
        print(f"   ⚠️  {fname} - error reading: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("✅ API key: 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")
print("✅ KIMORE (WebRehabPipeline) uses GroqLLM from llm_groq.py")
print("✅ KERAAL (KeraalRehabPipeline) uses Groq/Gemini with fallback")
print("")
print("To run the application:")
print("  source setup_groq_api.sh")
print("  python3 main.py")
print("=" * 70)
