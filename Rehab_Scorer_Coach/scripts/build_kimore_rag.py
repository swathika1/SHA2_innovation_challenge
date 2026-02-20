# Rehab_Scorer_Coach/scripts/build_kimore_rag.py
from pathlib import Path
from Rehab_Scorer_Coach.src.rag_store import RAGStore

def build_docs():
    # You can later replace these with official physio PDFs/links you collect.
    # For now: high-quality guidance text you control (stable + no scraping headaches).

    docs = []

    def add(exercise, title, body, source="Internal curated rehab guide"):
        doc_id = f"{exercise}:{title}".replace(" ", "_").lower()
        docs.append({
            "id": doc_id,
            "exercise": exercise,
            "source": source,
            "text": f"EXERCISE: {exercise}\nSECTION: {title}\n\n{body}".strip()
        })

    add("lifting_arms",
        "How to perform",
        """Stand tall with feet hip-width apart. Arms by your sides. Slowly raise both arms forward and up overhead.
Keep ribs down (don’t flare). Keep neck relaxed. Stop if painful. Lower with control.""")
    add("lifting_arms",
        "Common mistakes",
        """Shrugging shoulders, arching lower back, rushing the movement, bending elbows excessively.""")
    add("lifting_arms",
        "Cues",
        """Shoulders down and away from ears. Engage core lightly. Move slow and controlled.""")

    add("lateral_trunk_tilt",
        "How to perform",
        """Stand tall. Keep arms straight (can be out to sides or overhead depending on plan).
Bend your trunk sideways without rotating. Keep hips level. Return to center slowly.""")
    add("lateral_trunk_tilt",
        "Common mistakes",
        """Rotating the torso, leaning forward/back, lifting one hip, collapsing the shoulder.""")
    add("lateral_trunk_tilt",
        "Cues",
        """Imagine sliding between two panes of glass. Keep pelvis stable. Control the return.""")

    add("trunk_rotation",
        "How to perform",
        """Stand with feet shoulder-width. Cross arms over chest (or hands on hips). Rotate trunk left/right
without twisting knees. Keep pelvis mostly stable. Move in comfortable range.""")
    add("trunk_rotation",
        "Common mistakes",
        """Over-rotating through hips, turning feet, bending sideways, holding breath.""")
    add("trunk_rotation",
        "Cues",
        """Rotate from ribcage. Keep knees soft. Exhale gently during rotation.""")

    add("pelvis_rotation_transverse",
        "How to perform",
        """Stand tall, hands on hips. Make small controlled pelvic circles on the transverse plane.
Think “belt buckle draws a circle.” Keep upper body quiet.""")
    add("pelvis_rotation_transverse",
        "Common mistakes",
        """Moving the whole trunk, big uncontrolled circles, locking knees, leaning forward.""")
    add("pelvis_rotation_transverse",
        "Cues",
        """Small smooth circles. Upper body steady. Core lightly engaged.""")

    add("squat",
        "How to perform",
        """Feet shoulder-width. Send hips back then bend knees. Keep chest up and spine neutral.
Knees track over toes. Go to comfortable depth. Push through mid-foot to stand.""")
    add("squat",
        "Common mistakes",
        """Knees cave inward, heels lifting, rounding lower back, knees shooting far past toes, rushing.""")
    add("squat",
        "Cues",
        """Knees in line with toes. Brace core. Slow down. Control descent and ascent.""")

    return docs

if __name__ == "__main__":
    persist_dir = Path(__file__).resolve().parents[1] / "rag_db"
    store = RAGStore(persist_dir=persist_dir)
    docs = build_docs()
    store.add_docs(docs)
    print(f"Built RAG store at {persist_dir} with {len(docs)} docs.")