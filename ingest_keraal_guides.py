"""
Ingest KERAAL exercise guides (PDFs) into RAG system for LLM context.

This script extracts text from KERAAL exercise PDFs and ingests them into
the FAISS vector database for use in generating context-aware feedback.
"""

import os
import sys
from pathlib import Path

# Try to import PyPDF2 or pdfplumber for PDF extraction
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# Import RAG engine
import rag_engine


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                return text
        except Exception as e:
            print(f"❌ Error extracting with pdfplumber: {e}")
            return ""
    
    elif HAS_PYPDF2:
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return text
        except Exception as e:
            print(f"❌ Error extracting with PyPDF2: {e}")
            return ""
    
    else:
        print("❌ Neither pdfplumber nor PyPDF2 installed. Install with: pip install pdfplumber")
        return ""


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list:
    """Split text into chunks with overlap."""
    chunks = []
    sentences = text.split('.')
    
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def ingest_keraal_guides():
    """Ingest all KERAAL guide PDFs into RAG system."""
    
    guides_dir = Path("Keraal_Guides")
    
    if not guides_dir.exists():
        print(f"❌ Keraal_Guides directory not found at {guides_dir.absolute()}")
        return False
    
    pdf_files = list(guides_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ No PDF files found in {guides_dir}")
        return False
    
    print(f"\n📚 Found {len(pdf_files)} PDF files")
    print("=" * 60)
    
    total_ingested = 0
    all_texts = []
    all_metadatas = []
    all_ids = []
    
    for pdf_path in pdf_files:
        print(f"\n🔄 Processing: {pdf_path.name}")
        
        # Extract text
        text = extract_text_from_pdf(str(pdf_path))
        
        if not text.strip():
            print(f"   ⚠️  No text extracted from {pdf_path.name}")
            continue
        
        print(f"   ✅ Extracted {len(text)} characters")
        
        # Chunk text
        chunks = chunk_text(text)
        print(f"   ✅ Created {len(chunks)} chunks")
        
        # Prepare for batch ingestion
        exercise_name = pdf_path.stem  # e.g., "Forward_Flexion"
        
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                all_texts.append(chunk)
                all_metadatas.append({
                    "type": "keraal_exercise",
                    "exercise": exercise_name,
                    "chunk": i,
                    "source": f"keraal_guide:{exercise_name}:{i}"
                })
                all_ids.append(f"keraal_{exercise_name}_{i}")
                total_ingested += 1
        
        print(f"   ✅ Prepared {len(chunks)} chunks from {exercise_name}")
    
    # Batch ingest all at once
    if all_texts:
        print(f"\n💾 Ingesting {len(all_texts)} chunks into RAG system...")
        try:
            rag_engine.ingest_texts(all_texts, all_metadatas, all_ids)
            print(f"   ✅ Successfully ingested all chunks")
        except Exception as e:
            print(f"   ❌ Error during ingestion: {e}")
            return False
    
    print("\n" + "=" * 60)
    print(f"✅ Successfully processed {total_ingested} chunks from KERAAL guides")
    print("=" * 60)
    
    return True


def check_keraal_guides_in_rag():
    """Check what KERAAL guides are in the RAG system."""
    
    print("\n📖 Checking KERAAL guides in RAG system...")
    print("=" * 60)
    
    # Query for each exercise
    exercises = ["Forward Flexion", "Flank Stretch", "Torso Rotation"]
    
    for exercise in exercises:
        print(f"\n🔍 Searching for: {exercise}")
        
        try:
            results = rag_engine.retrieve(exercise, top_k=1)
            
            if results:
                print(f"   ✅ Found relevant context:")
                lines = results.split('\n')[:3]
                for line in lines:
                    preview = line[:80] if len(line) > 80 else line
                    print(f"      {preview}")
            else:
                print(f"   ⚠️  No results found")
        except Exception as e:
            print(f"   ⚠️  Note: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🎯 KERAAL Guide RAG Ingestion")
    print("=" * 60)
    
    # Check if PDFs are extracted
    import subprocess
    try:
        import pdfplumber
        print("✅ pdfplumber is available")
    except ImportError:
        print("⚠️  pdfplumber not available, trying to install...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pdfplumber", "-q"], check=False)
    
    # Ingest guides
    success = ingest_keraal_guides()
    
    if success:
        # Verify ingestion
        check_keraal_guides_in_rag()
        print("\n✅ KERAAL guides successfully ingested into RAG!")
    else:
        print("\n❌ Failed to ingest KERAAL guides")
        sys.exit(1)
