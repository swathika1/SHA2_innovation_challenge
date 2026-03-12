"""
ingest_rag_documents.py — Ingest PDFs from rag_documents/RAG/ into ChromaDB.

Usage:
    python ingest_rag_documents.py
"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from pypdf import PdfReader
from Rehab_Scorer_Coach.src.rag_store import RAGStore

PDF_DIR = Path(__file__).parent / "rag_documents" / "RAG"
RAG_DIR = Path(__file__).parent / "Rehab_Scorer_Coach" / "rag_db"

EXERCISE_KEYWORDS = {
    "squat": ["squat", "sit to stand"],
    "lifting_arms": ["shoulder flexion", "arm raise", "shoulder raise", "arms overhead"],
    "lateral_trunk_tilt": ["side bend", "lateral flexion", "trunk tilt"],
    "trunk_rotation": ["trunk rotation", "spinal rotation", "thoracic rotation", "torso rotation"],
    "forward_flexion": ["forward flexion", "hip hinge", "forward bend", "toe touch"],
    "flank_stretch": ["flank stretch", "side stretch", "lateral stretch"],
    "acl_rehabilitation": ["acl", "anterior cruciate", "ligament"],
    "shoulder_rehabilitation": ["shoulder", "rotator cuff", "glenohumeral"],
    "lower_limb": ["lower limb", "leg strength", "knee", "hip strength"],
    "upper_limb": ["upper limb", "arm strength"],
}


def guess_exercise(text: str, filename: str) -> str:
    blob = (filename + "\n" + text[:2000]).lower()
    for ex, kws in EXERCISE_KEYWORDS.items():
        if any(kw in blob for kw in kws):
            return ex
    return "general"


def clean_text(s: str) -> str:
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150):
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += chunk_size - overlap
    return chunks


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for p in reader.pages:
        t = p.extract_text() or ""
        if t.strip():
            pages.append(t)
    return "\n\n".join(pages)


def main():
    if not PDF_DIR.exists():
        raise SystemExit(f"PDF folder not found: {PDF_DIR}")

    store = RAGStore(persist_dir=RAG_DIR)
    docs = []
    doc_id_prefix = "rag_documents"

    pdfs = list(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {PDF_DIR}")

    print(f"Found {len(pdfs)} PDFs in {PDF_DIR}\n")

    for pdf in pdfs:
        try:
            raw = extract_pdf_text(pdf)
        except Exception as e:
            print(f"  ERROR reading {pdf.name}: {e}")
            continue

        text = clean_text(raw)
        if len(text) < 50:
            print(f"  SKIP (no extractable text): {pdf.name}")
            continue

        exercise = guess_exercise(text, pdf.name)
        chunks = chunk_text(text)

        for idx, ch in enumerate(chunks):
            doc_id = f"{doc_id_prefix}::{pdf.stem}::chunk{idx}"
            docs.append({
                "id": doc_id,
                "exercise": exercise,
                "source": f"PDF:{pdf.name}",
                "text": f"SOURCE: {pdf.name}\nEXERCISE: {exercise}\n\n{ch}".strip(),
            })

        print(f"  OK  {pdf.name}  ->  {len(chunks)} chunks  (exercise={exercise})")

    if docs:
        store.add_docs(docs)
        print(f"\nDone. Added {len(docs)} chunks into ChromaDB at {RAG_DIR}")
    else:
        print("\nNo docs added. Check PDF text extraction.")


if __name__ == "__main__":
    main()
