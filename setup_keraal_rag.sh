#!/bin/bash
# setup_keraal_rag.sh - Setup KERAAL RAG system with exercise guides

echo "🎯 Setting up KERAAL RAG System"
echo "======================================"

# Check if pdfplumber is installed
echo "📦 Checking dependencies..."
python3 -c "import pdfplumber" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Installing pdfplumber..."
    pip install pdfplumber -q
fi

# Ingest KERAAL guides
echo ""
echo "📚 Ingesting KERAAL exercise guides into RAG system..."
python3 ingest_keraal_guides.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ KERAAL RAG setup complete!"
    echo "======================================"
    echo ""
    echo "📖 Exercise guides ingested:"
    echo "   • Forward Flexion"
    echo "   • Flank Stretch"
    echo "   • Torso Rotation"
    echo ""
    echo "🚀 Ready to start Flask with RAG-enhanced feedback:"
    echo "   python3 main.py"
else
    echo ""
    echo "❌ Setup failed"
    exit 1
fi
