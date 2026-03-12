#!/bin/bash

# Setup Groq API Key for KERAAL and KIMORE pipelines
# This script exports the GROQ_API_KEY environment variable

export GROQ_API_KEY="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"

echo "✅ GROQ_API_KEY has been set"
echo "📋 Current value: ${GROQ_API_KEY:0:20}..." # Show first 20 chars

# Optional: Set model (defaults to llama-3.1-8b-instant)
export GROQ_MODEL="llama-3.1-8b-instant"
echo "✅ GROQ_MODEL set to: $GROQ_MODEL"

# To use this script:
# 1. Run: source setup_groq_api.sh
# 2. Then: python3 main.py

echo ""
echo "🚀 Ready to start the application!"
echo "   Run: python3 main.py"
