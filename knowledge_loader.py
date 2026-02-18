"""
knowledge_loader.py - Load knowledge sources into RAG vector store.

Usage:
    python knowledge_loader.py --all           # Load everything
    python knowledge_loader.py --kimore        # KIMORE dataset only
    python knowledge_loader.py --exercises     # DB exercises only
    python knowledge_loader.py --documents     # PDFs/text files only
    python knowledge_loader.py --add path.pdf  # Add a single document
"""
import os
import sys
import sqlite3
import argparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from rag_engine import ingest_texts, get_stats

BASE_DIR = os.path.dirname(__file__)
DOCUMENTS_DIR = os.path.join(BASE_DIR, "rag_documents")
KIMORE_DIR = os.path.join(BASE_DIR, "kimore_knowledge")


# ==================== KIMORE DATASET ====================

KIMORE_EXERCISES = {
    "Ex1": {
        "name": "Lifting of the arms",
        "description": "Standing with arms along the body, lift both arms laterally "
                       "until they are above the head, then return to starting position.",
        "target": "Shoulder mobility, upper limb coordination",
        "clinical_focus": "Range of motion of the shoulder joint, symmetry of movement",
        "common_issues": "Asymmetric arm raise, insufficient range, compensatory trunk movement",
        "rehab_context": "Used for low back pain rehabilitation to improve upper body mobility "
                         "and posture. Helps patients regain shoulder flexibility post-injury."
    },
    "Ex2": {
        "name": "Lateral tilt of the trunk",
        "description": "Standing upright, tilt the trunk laterally to the left and right, "
                       "keeping arms along the body.",
        "target": "Trunk lateral flexibility, core stability",
        "clinical_focus": "Lateral trunk range of motion, symmetry between left and right",
        "common_issues": "Limited range on affected side, hip compensation, uneven tilt angles",
        "rehab_context": "Core exercise for low back pain patients. Lateral trunk mobility "
                         "is crucial for daily activities like reaching and bending."
    },
    "Ex3": {
        "name": "Trunk rotation",
        "description": "Standing upright with hands on hips, rotate the trunk left and right.",
        "target": "Trunk rotational mobility, spinal flexibility",
        "clinical_focus": "Rotational range of motion, smoothness of movement",
        "common_issues": "Jerky movements, limited rotation range, compensatory hip rotation",
        "rehab_context": "Important for restoring functional spinal rotation needed in walking, "
                         "driving, and household activities."
    },
    "Ex4": {
        "name": "Pelvis rotation on the transversal plane (squatting)",
        "description": "Perform a squat movement, bending knees while keeping the trunk upright.",
        "target": "Lower limb strength, knee stability, hip mobility",
        "clinical_focus": "Knee flexion angle, trunk uprightness, symmetry of descent",
        "common_issues": "Insufficient depth, forward trunk lean, knee valgus, asymmetric loading",
        "rehab_context": "Functional exercise for building lower body strength. Critical for "
                         "patients recovering from knee or hip procedures who need to regain "
                         "ability to sit, stand, and climb stairs."
    },
    "Ex5": {
        "name": "Rotation of the trunk and target touching",
        "description": "Standing upright, rotate trunk and reach toward targets placed at "
                       "various positions, combining rotation with arm extension.",
        "target": "Coordination, trunk rotation with upper limb reaching",
        "clinical_focus": "Accuracy of target touching, combined trunk-arm coordination",
        "common_issues": "Inaccurate reaching, excessive trunk compensation, slow movements",
        "rehab_context": "Most complex KIMORE exercise, testing functional coordination. "
                         "Mimics real-world reaching tasks during daily living."
    }
}

KIMORE_SCORING_KNOWLEDGE = [
    "The KIMORE dataset uses a dual scoring system: Primary Outcome (PO) scores range 0-15 "
    "measuring the quality of the target movement, and Control Factor (CF) scores range 0-35 "
    "measuring physical constraints. Total score ranges 0-50, where higher is better.",

    "In KIMORE assessment, a score below 25/50 indicates significant movement dysfunction "
    "requiring close monitoring. Scores 25-40 indicate moderate rehabilitation progress. "
    "Scores above 40 indicate near-normal movement quality.",

    "KIMORE exercise quality assessment considers: range of motion, movement symmetry, "
    "smoothness of execution, compensatory movements, and timing consistency. "
    "Compensatory movements (like trunk lean during arm raises) reduce the score.",

    "The KIMORE dataset validated its scoring against stereophotogrammetric systems "
    "(gold standard for motion capture). The kinematic features were defined and validated "
    "by physicians specializing in physical rehabilitation.",

    "For rehabilitation monitoring, declining KIMORE-style scores across sessions may indicate "
    "fatigue, pain avoidance, or regression. Consistently improving scores suggest the "
    "rehabilitation program is effective and the patient is progressing.",

    "KIMORE's population included 44 healthy subjects and 34 with motor dysfunctions. "
    "The healthy baselines provide reference ranges for what 'normal' movement looks like "
    "for each exercise type.",

    "When a patient reports knee pain during squats (KIMORE Ex4), common modifications include: "
    "reducing squat depth, using wall support, switching to sit-to-stand from a chair, "
    "or performing partial range mini-squats. Pain above 5/10 during exercise should trigger "
    "a plan modification discussion with the clinician.",

    "For shoulder rehabilitation exercises (KIMORE Ex1 - arm lifting), patients should aim for "
    "gradual range increase. Week 1-2: lift to 90 degrees. Week 3-4: lift to 135 degrees. "
    "Week 5+: full overhead range. Asymmetry greater than 15 degrees between arms needs attention.",

    "Trunk rotation exercises (KIMORE Ex3) are contraindicated for patients with acute disc "
    "herniation or recent spinal surgery. For post-surgical patients, start trunk rotation "
    "only after clearance from the surgeon, typically 6-8 weeks post-operation."
]


def load_kimore():
    """Process KIMORE dataset knowledge into embeddable chunks."""
    texts = []
    metadatas = []

    for ex_id, ex_data in KIMORE_EXERCISES.items():
        chunk = (
            f"Exercise: {ex_data['name']} ({ex_id}). "
            f"{ex_data['description']} "
            f"Target: {ex_data['target']}. "
            f"Clinical focus: {ex_data['clinical_focus']}. "
            f"Common issues: {ex_data['common_issues']}. "
            f"Rehabilitation context: {ex_data['rehab_context']}"
        )
        texts.append(chunk)
        metadatas.append({"source": "kimore", "exercise_id": ex_id, "type": "exercise"})

    for i, text in enumerate(KIMORE_SCORING_KNOWLEDGE):
        texts.append(text)
        metadatas.append({"source": "kimore", "type": "scoring", "chunk_index": str(i)})

    # Load any supplementary .txt files from kimore_knowledge/
    if os.path.isdir(KIMORE_DIR):
        for fname in sorted(os.listdir(KIMORE_DIR)):
            fpath = os.path.join(KIMORE_DIR, fname)
            if fname.endswith(".txt"):
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
                paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                for j, para in enumerate(paragraphs):
                    if len(para) > 50:
                        texts.append(para[:500])
                        metadatas.append({
                            "source": "kimore", "type": "supplementary",
                            "file": fname, "chunk_index": str(j)
                        })

    ingest_texts(texts, metadatas)
    print(f"[KIMORE] Loaded {len(texts)} chunks")


# ==================== DATABASE EXERCISES ====================

def load_exercises_from_db():
    """Extract exercise knowledge from rehab_coach.db."""
    db_path = os.path.join(BASE_DIR, "rehab_coach.db")
    if not os.path.exists(db_path):
        print("[DB] rehab_coach.db not found, skipping")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    texts = []
    metadatas = []

    # Load exercises
    try:
        cursor.execute("SELECT * FROM exercises")
        exercises = cursor.fetchall()
        for ex in exercises:
            chunk = (
                f"Exercise: {ex['name']}. "
                f"Category: {ex['category'] or 'General'}. "
                f"Difficulty: {ex['difficulty']}/5. "
                f"Description: {ex['description'] or 'Standard rehabilitation exercise.'}"
            )
            texts.append(chunk)
            metadatas.append({
                "source": "exercises", "type": "exercise",
                "exercise_id": str(ex['id'])
            })
    except Exception as e:
        print(f"[DB] Could not load exercises: {e}")

    # Load aggregate session patterns (anonymized)
    try:
        cursor.execute("""
            SELECT e.name, e.category,
                   AVG(s.quality_score) as avg_quality,
                   AVG(s.pain_after) as avg_pain,
                   COUNT(*) as session_count
            FROM sessions s
            JOIN workouts w ON s.workout_id = w.id
            JOIN exercises e ON w.exercise_id = e.id
            GROUP BY e.id
            HAVING session_count >= 3
        """)
        patterns = cursor.fetchall()
        for p in patterns:
            chunk = (
                f"Exercise pattern: {p['name']} ({p['category'] or 'General'}) - "
                f"Based on {p['session_count']} sessions, average quality score is "
                f"{p['avg_quality']:.0f}/100 and average post-exercise pain is "
                f"{p['avg_pain']:.1f}/10. "
            )
            if p['avg_pain'] and p['avg_pain'] > 5:
                chunk += "This exercise tends to cause significant pain and may need modification. "
            if p['avg_quality'] and p['avg_quality'] < 50:
                chunk += "Patients often struggle with form on this exercise. "
            texts.append(chunk)
            metadatas.append({
                "source": "exercises", "type": "session_pattern",
                "exercise_name": p['name']
            })
    except Exception as e:
        print(f"[DB] Could not load session patterns: {e}")

    conn.close()
    ingest_texts(texts, metadatas)
    print(f"[DB] Loaded {len(texts)} chunks from rehab_coach.db")


# ==================== DOCUMENT PIPELINE ====================

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            last_period = chunk.rfind(".")
            if last_period > chunk_size // 2:
                end = start + last_period + 1
                chunk = text[start:end]
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if len(c) > 50]


def _extract_pdf_text(filepath: str) -> str:
    """Extract text from a PDF file."""
    try:
        import PyPDF2
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except ImportError:
        print("[WARN] PyPDF2 not installed. Install with: pip install PyPDF2")
        return ""


def load_document(filepath: str):
    """Load a single document (PDF or text) into the vector store."""
    if not os.path.exists(filepath):
        print(f"[DOC] File not found: {filepath}")
        return

    fname = os.path.basename(filepath)

    if filepath.endswith(".pdf"):
        text = _extract_pdf_text(filepath)
    elif filepath.endswith((".txt", ".md")):
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        print(f"[DOC] Unsupported format: {filepath} (use .pdf, .txt, or .md)")
        return

    if not text.strip():
        print(f"[DOC] No text extracted from {filepath}")
        return

    chunks = _chunk_text(text)
    metadatas = [{"source": "documents", "type": "document", "file": fname,
                  "chunk_index": str(i)} for i in range(len(chunks))]

    ingest_texts(chunks, metadatas)
    print(f"[DOC] Loaded {len(chunks)} chunks from {fname}")


def load_all_documents():
    """Load all documents from rag_documents/ directory."""
    if not os.path.isdir(DOCUMENTS_DIR):
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        print(f"[DOC] Created {DOCUMENTS_DIR}/ — place PDF/txt files here")
        return

    files = [f for f in os.listdir(DOCUMENTS_DIR)
             if f.endswith((".pdf", ".txt", ".md"))]

    if not files:
        print(f"[DOC] No documents found in {DOCUMENTS_DIR}/")
        return

    for fname in sorted(files):
        load_document(os.path.join(DOCUMENTS_DIR, fname))


# ==================== CLI ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load knowledge into RAG vector store")
    parser.add_argument("--all", action="store_true", help="Load all sources")
    parser.add_argument("--kimore", action="store_true", help="Load KIMORE dataset")
    parser.add_argument("--exercises", action="store_true", help="Load DB exercises")
    parser.add_argument("--documents", action="store_true", help="Load all documents")
    parser.add_argument("--add", type=str, help="Add a single document file")
    args = parser.parse_args()

    if args.all or not any([args.kimore, args.exercises, args.documents, args.add]):
        load_kimore()
        load_exercises_from_db()
        load_all_documents()
    else:
        if args.kimore:
            load_kimore()
        if args.exercises:
            load_exercises_from_db()
        if args.documents:
            load_all_documents()
        if args.add:
            load_document(args.add)

    stats = get_stats()
    print(f"\nVector store: {stats['total_chunks']} total chunks in {stats['store_dir']}")
