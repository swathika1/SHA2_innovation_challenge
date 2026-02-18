from pathlib import Path
import re
from pypdf import PdfReader

from Rehab_Scorer_Coach.src.rag_store import RAGStore

PDF_DIR = Path(__file__).resolve().parents[1] / "assets" / "rag_pdfs"
RAG_DIR = Path(__file__).resolve().parents[1] / "rag_db"

# Map filenames (or keywords inside PDF) to an exercise label for filtering
EXERCISE_KEYWORDS = {
    "lifting_arms": ["shoulder flexion", "arms overhead", "arm raise", "shoulder raise"],
    "lateral_trunk_tilt": ["side bend", "lateral flexion", "trunk tilt"],
    "trunk_rotation": ["trunk rotation", "spinal rotation", "thoracic rotation"],
    "pelvis_rotation_transverse": ["pelvic tilt", "pelvic rotation", "pelvis circles", "hip circles"],
    "squat": ["squat", "sit to stand", "chair squat"],
}

def guess_exercise(text: str, filename: str) -> str:  # sourcery skip: use-next
    blob = (filename + "\n" + text).lower()
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
    # simple char-based chunking (good enough for PDFs)
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+chunk_size])
        i += (chunk_size - overlap)
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
        raise SystemExit(f"PDF folder not found: {PDF_DIR}. Create it and add PDFs.")

    store = RAGStore(persist_dir=RAG_DIR)
    docs = []

    for pdf in PDF_DIR.glob("*.pdf"):
        raw = extract_pdf_text(pdf)
        text = clean_text(raw)
        if len(text) < 50:
            print(f"⚠️ Skipping (no extractable text): {pdf.name}")
            continue

        exercise = guess_exercise(text, pdf.name)
        chunks = chunk_text(text)

        for idx, ch in enumerate(chunks):
            doc_id = f"pdf::{pdf.stem}::chunk{idx}"
            docs.append({
                "id": doc_id,
                "exercise": exercise,
                "source": f"PDF:{pdf.name}",
                "text": f"SOURCE: {pdf.name}\nEXERCISE: {exercise}\n\n{ch}".strip()
            })

        print(f"✅ Ingested {pdf.name} -> {len(chunks)} chunks (exercise={exercise})")

    if docs:
        store.add_docs(docs)
        print(f"\n🎉 Done. Added {len(docs)} chunks into {RAG_DIR}")
    else:
        print("\n⚠️ No docs added. Check PDF text extraction.")

if __name__ == "__main__":
    main()