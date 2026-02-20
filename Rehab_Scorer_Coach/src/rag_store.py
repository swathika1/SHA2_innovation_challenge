# Rehab_Scorer_Coach/src/rag_store.py
from __future__ import annotations
import os
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TF"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float

class RAGStore:
    """
    Local RAG store for exercise instructions.
    Backed by Chroma (persistent on disk).
    """
    def __init__(self, persist_dir: Path):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        from chromadb import PersistentClient
        from chromadb.utils import embedding_functions

        # Small/free embedding model (local CPU)
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._client = PersistentClient(path=str(self.persist_dir))
        self._col = self._client.get_or_create_collection(
            name="exercise_docs",
            embedding_function=self._embed_fn
        )

    def add_docs(self, docs: List[Dict]):
        """
        docs: [{"id": "...", "text": "...", "source": "...", "exercise": "..."}]
        """
        ids = [d["id"] for d in docs]
        texts = [d["text"] for d in docs]
        metas = [{"source": d.get("source", ""), "exercise": d.get("exercise", "")} for d in docs]
        self._col.upsert(ids=ids, documents=texts, metadatas=metas)

    def query(self, query_text: str, exercise: Optional[str] = None, k: int = 4) -> List[RetrievedChunk]:
        where = {"exercise": exercise} if exercise else None
        res = self._col.query(query_texts=[query_text], n_results=k, where=where)

        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        out: List[RetrievedChunk] = []
        for text, meta, dist in zip(docs, metas, dists):
            # Convert distance to a "score-like" number (smaller dist = better)
            score = float(1.0 / (1.0 + dist)) if dist is not None else 0.0
            out.append(RetrievedChunk(text=text, source=meta.get("source",""), score=score))
        return out