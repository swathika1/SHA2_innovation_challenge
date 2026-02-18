"""
rag_engine.py - RAG engine using FAISS + sentence-transformers.
Provides retrieve() for the chat pipeline and ingest functions for loading knowledge.
"""
import os
import json
import hashlib
import numpy as np
import faiss
from typing import List, Optional

BASE_DIR = os.path.dirname(__file__)
STORE_DIR = os.path.join(BASE_DIR, "vector_store")
INDEX_PATH = os.path.join(STORE_DIR, "faiss.index")
META_PATH = os.path.join(STORE_DIR, "metadata.json")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_TOP_K = 3
SIMILARITY_THRESHOLD = 0.35  # minimum cosine similarity to include a result

# Lazy-loaded singletons
_model = None
_index = None
_metadata = None  # list of {"id": str, "text": str, "source": str, ...}


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _load_store():
    """Load FAISS index and metadata from disk."""
    global _index, _metadata
    if _index is not None:
        return

    os.makedirs(STORE_DIR, exist_ok=True)

    if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        _index = faiss.read_index(INDEX_PATH)
        with open(META_PATH, "r", encoding="utf-8") as f:
            _metadata = json.load(f)
    else:
        # Create empty index (384 = all-MiniLM-L6-v2 dimension)
        _index = faiss.IndexFlatIP(384)  # inner product (cosine after normalization)
        _metadata = []


def _save_store():
    """Persist FAISS index and metadata to disk."""
    os.makedirs(STORE_DIR, exist_ok=True)
    faiss.write_index(_index, INDEX_PATH)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(_metadata, f, ensure_ascii=False)


def _embed(texts: List[str]) -> np.ndarray:
    """Embed texts and L2-normalize for cosine similarity via inner product."""
    model = _get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    faiss.normalize_L2(embeddings)
    return embeddings


def retrieve(query: str, top_k: int = DEFAULT_TOP_K,
             source_filter: Optional[str] = None) -> str:
    """
    Retrieve relevant chunks for a user query.
    Returns a formatted string ready to inject into MeriLion instruction.
    Returns empty string if no relevant results.
    """
    _load_store()

    if _index.ntotal == 0:
        return ""

    query_vec = _embed([query])
    k = min(top_k * 2, _index.ntotal)  # fetch extra to allow filtering
    scores, indices = _index.search(query_vec, k)

    chunks = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_metadata):
            continue
        if score < SIMILARITY_THRESHOLD:
            continue
        entry = _metadata[idx]
        if source_filter and entry.get("source") != source_filter:
            continue
        chunks.append(entry["text"])
        if len(chunks) >= top_k:
            break

    if not chunks:
        return ""

    formatted = "Relevant rehabilitation knowledge:\n"
    for chunk in chunks:
        formatted += f"- {chunk}\n"

    return formatted.strip()


def ingest_texts(texts: List[str], metadatas: List[dict],
                 ids: Optional[List[str]] = None):
    """Add text chunks to the vector store. Deduplicates by ID."""
    _load_store()

    if ids is None:
        ids = [hashlib.md5(t.encode()).hexdigest()[:16] for t in texts]

    # Build set of existing IDs for dedup
    existing_ids = {m["id"] for m in _metadata}

    new_texts = []
    new_metas = []
    for text, meta, doc_id in zip(texts, metadatas, ids):
        if doc_id not in existing_ids:
            new_texts.append(text)
            new_metas.append({**meta, "id": doc_id, "text": text})

    if not new_texts:
        return

    embeddings = _embed(new_texts)
    _index.add(embeddings)
    _metadata.extend(new_metas)
    _save_store()


def get_stats() -> dict:
    """Return store statistics."""
    _load_store()
    return {
        "total_chunks": _index.ntotal,
        "store_dir": STORE_DIR
    }
