#!/bin/bash
# Setup LLM API Keys for KERAAL Feedback System

# Option 1: Groq (RECOMMENDED - Faster and free tier available)
# Get API key from: https://console.groq.com/keys
export GROQ_API_KEY="your-groq-api-key-here"

# Option 2: Google Gemini (Fallback)
# Get API key from: https://makersuite.google.com/app/apikey
export GOOGLE_API_KEY="your-google-api-key-here"

# Then run:
# python3 main.py

echo "✅ API keys configured"
echo "Run: python3 main.py"
