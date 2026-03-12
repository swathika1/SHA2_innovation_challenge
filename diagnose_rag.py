#!/usr/bin/env python3
"""
Deep dive: What's actually IN the RAG databases?
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

print("="*80)
print("RAG DATABASE CONTENT ANALYSIS")
print("="*80)

# Test 1: Inspect ChromaDB directly
print("\n✅ TEST 1: INSPECT CHROMADB CONTENTS")
print("-" * 80)

try:
    import chromadb
    from chromadb.config import Settings
    
    rag_db_path = Path(__file__).parent / "rag_db"
    
    # Try to connect to existing ChromaDB
    client = chromadb.PersistentClient(path=str(rag_db_path))
    collections = client.list_collections()
    
    print(f"\n  ChromaDB found at: {rag_db_path}")
    print(f"  Number of collections: {len(collections)}")
    
    if collections:
        for col in collections:
            print(f"\n  Collection: {col.name if hasattr(col, 'name') else col}")
            try:
                # Get collection
                if hasattr(col, 'name'):
                    collection = client.get_collection(name=col.name)
                else:
                    collection = client.get_collection(name=str(col))
                
                # Count documents
                count = collection.count()
                print(f"    Documents: {count}")
                
                # Sample documents
                if count > 0:
                    results = collection.get(limit=3)
                    print(f"    Sample documents:")
                    for i, (doc_id, doc_text) in enumerate(zip(
                        results.get('ids', []),
                        results.get('documents', [])
                    ), 1):
                        preview = doc_text[:100] if isinstance(doc_text, str) else str(doc_text)[:100]
                        print(f"      {i}. ID={doc_id} | Text: {preview}...")
            except Exception as e:
                print(f"    Error inspecting collection: {e}")
    else:
        print("  ⚠️  NO COLLECTIONS FOUND - ChromaDB is EMPTY!")

except Exception as e:
    print(f"  ⚠️  Could not inspect ChromaDB: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check what RAGStore sees
print("\n✅ TEST 2: RAGSTORE INSPECTION")
print("-" * 80)

try:
    from Rehab_Scorer_Coach.src.rag_store import RAGStore
    
    rag_db_path = Path(__file__).parent / "rag_db"
    rag = RAGStore(persist_dir=rag_db_path)
    
    print(f"\n  RAGStore initialized from: {rag_db_path}")
    
    # Try query with very broad terms
    broad_queries = [
        "exercise",
        "form",
        "squat",
        "stretch",
        "",  # Empty query
        "a"   # Single char
    ]
    
    for query in broad_queries:
        try:
            results = rag.query(query_text=query, k=5)
            print(f"\n  Query '{query}': {len(results)} results")
            if results:
                for i, result in enumerate(results[:2], 1):
                    text = result.text if hasattr(result, 'text') else str(result)
                    preview = text[:80]
                    print(f"    {i}. {preview}...")
        except Exception as query_err:
            print(f"  Query '{query}' failed: {query_err}")

except Exception as e:
    print(f"  ❌ RAGStore error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check Documentation files
print("\n✅ TEST 3: RAG DOCUMENTS FOLDER")
print("-" * 80)

try:
    rag_docs_path = Path(__file__).parent / "rag_documents"
    if rag_docs_path.exists():
        print(f"\n  RAG documents folder found: {rag_docs_path}")
        files = list(rag_docs_path.glob("*"))
        print(f"  Files: {len(files)}")
        for f in files[:10]:
            size = f.stat().st_size / 1024 if f.is_file() else "DIR"
            print(f"    - {f.name} ({size} KB)" if isinstance(size, str) else f"    - {f.name} ({size:.1f} KB)")
    else:
        print(f"  ⚠️  rag_documents folder NOT found")

except Exception as e:
    print(f"  ⚠️  Could not check rag_documents: {e}")

# Test 4: Run document ingestion test
print("\n✅ TEST 4: ATTEMPT TO REINGEST DATA")
print("-" * 80)

try:
    print("\n  Checking if ingest scripts exist...")
    ingest_scripts = [
        "ingest_rag_documents.py",
        "populate_rag_chromadb.py",
        "knowledge_loader.py"
    ]
    
    base_path = Path(__file__).parent
    for script in ingest_scripts:
        script_path = base_path / script
        if script_path.exists():
            print(f"  ✓ Found: {script}")
        else:
            print(f"  ✗ Missing: {script}")

except Exception as e:
    print(f"  ⚠️  Error checking scripts: {e}")

# Test 5: Try RAG with different query methods
print("\n✅ TEST 5: ALTERNATIVE QUERY METHODS")
print("-" * 80)

try:
    from Rehab_Scorer_Coach.src.rag_store import RAGStore
    
    rag = RAGStore(persist_dir=Path(__file__).parent / "rag_db")
    
    # Try different query patterns
    test_queries = [
        {"query_text": "squat proper form", "exercise": "squat"},
        {"query_text": "lifting heavy objects", "exercise": "lifting_of_arms"},
        {"query_text": "trunk movements", "exercise": "trunk_rotation"},
    ]
    
    for test in test_queries:
        try:
            results = rag.query(**test, k=3)
            print(f"\n  Query with filters {test}: {len(results)} results")
        except Exception as e:
            print(f"\n  Query {test} failed: {e}")

except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 6: Jimmy Avatar with Flask context
print("\n✅ TEST 6: JIMMY AVATAR WITH PROPER CONTEXT")
print("-" * 80)

try:
    # Try to create Flask context for database access
    from main import app
    
    with app.app_context():
        from meralion_avatar import AvatarJimmy
        avatar = AvatarJimmy()
        
        # Try with a real or test patient ID
        context = avatar.get_patient_context(patient_id=1)
        print(f"\n  Patient context (ID 1):")
        print(f"  {context[:200]}...")
        
        # Test with non-existent ID
        context2 = avatar.get_patient_context(patient_id=99999)
        print(f"\n  Patient context (ID 99999):")
        print(f"  {context2[:200]}...")

except Exception as e:
    print(f"  ⚠️  Could not test with Flask context: {e}")
    print("     This is likely a Flask app context issue, not Jimmy's fault")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
print("""
FINDINGS:
────────────────────────────────────────────────────────────────────────────────
If RAG returned 0 results → Database is likely EMPTY and needs data ingestion
If ChromaDB shows 0 collections → Need to run ingest_rag_documents.py
If rag_documents folder is empty → Need to populate it with exercise guides

NEXT STEP:
────────────────────────────────────────────────────────────────────────────────
Run one of these to populate the RAG database:
  python3 ingest_rag_documents.py
  python3 populate_rag_chromadb.py
  python3 knowledge_loader.py
""")
