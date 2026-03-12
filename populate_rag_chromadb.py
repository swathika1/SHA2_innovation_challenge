"""
populate_rag_chromadb.py — Populate ChromaDB RAG with comprehensive exercise knowledge
for BOTH Kimore and Keraal pipelines.

This ensures the live pipelines (web_pipeline.py, keraal_pipeline.py) have rich
exercise-specific knowledge for generating accurate LLM feedback.

Usage:
    python populate_rag_chromadb.py
"""

import sys
import os
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from Rehab_Scorer_Coach.src.rag_store import RAGStore

RAG_DIR = Path(__file__).parent / "rag_db"


# =====================================================================
# KIMORE EXERCISES — Comprehensive Form Guidance
# =====================================================================

KIMORE_KNOWLEDGE = {
    "squat": [
        {
            "text": "Squat exercise: Stand with feet shoulder-width apart. Lower your hips by bending your knees, keeping your back straight and chest up. Aim for hip crease to reach knee level. Push through your heels to return to standing. This is KIMORE Exercise 4 (Pelvis rotation on transversal plane).",
            "source": "kimore_guide"
        },
        {
            "text": "Squat common mistakes: Forward trunk lean — keep chest upright and core engaged. Knee valgus (knees caving inward) — push knees outward in line with toes. Insufficient depth — work toward thighs parallel to floor. Heels lifting — weight should remain on heels. Asymmetric loading — distribute weight evenly on both legs.",
            "source": "kimore_guide"
        },
        {
            "text": "Squat corrections: If you lean forward, widen your stance slightly and focus on sitting back into the squat. If knees cave in, place a resistance band above the knees to train proper tracking. If heels lift, elevate heels on a small plate or work on ankle mobility. For pain during squats reduce depth, use wall support, or switch to sit-to-stand from a chair.",
            "source": "kimore_guide"
        },
        {
            "text": "Squat rehabilitation targets: Lower limb strength, knee stability, hip mobility. Clinical focus: Knee flexion angle, trunk uprightness, symmetry of descent. The KIMORE scoring system evaluates squat quality on a 0-50 scale where Primary Outcome (movement quality) is 0-15 and Control Factor (physical constraints) is 0-35.",
            "source": "kimore_guide"
        },
    ],
    "lifting_of_arms": [
        {
            "text": "Lifting of Arms exercise: Standing with arms along your body, lift both arms laterally until they are above your head, then return to the starting position. Keep elbows slightly bent. This is KIMORE Exercise 1.",
            "source": "kimore_guide"
        },
        {
            "text": "Lifting of Arms common mistakes: Asymmetric arm raise — both arms should move at the same speed and height. Insufficient range of motion — aim for full overhead raise. Compensatory trunk movement — keep your torso still, do not lean. Shrugging shoulders — keep shoulders relaxed and down. Jerky movements — move smoothly and controlled.",
            "source": "kimore_guide"
        },
        {
            "text": "Lifting of Arms corrections: If one arm lags behind, focus on the weaker side with lighter range first. If you shrug your shoulders, consciously press them down before lifting. If range is limited: Week 1-2 lift to 90 degrees, Week 3-4 lift to 135 degrees, Week 5+ full overhead. Asymmetry greater than 15 degrees between arms needs clinical attention.",
            "source": "kimore_guide"
        },
        {
            "text": "Lifting of Arms rehabilitation targets: Shoulder mobility, upper limb coordination. Clinical focus: Range of motion of the shoulder joint, symmetry of movement. Important for patients recovering from shoulder injuries or surgery to regain flexibility and functional reaching ability.",
            "source": "kimore_guide"
        },
    ],
    "lateral_trunk_tilt": [
        {
            "text": "Lateral Trunk Tilt exercise: Stand upright with feet shoulder-width apart. Slowly tilt your trunk to one side (20-30 degrees), return to center, then tilt to the other side. Keep arms along the body. This is KIMORE Exercise 2.",
            "source": "kimore_guide"
        },
        {
            "text": "Lateral Trunk Tilt common mistakes: Limited range on affected side — gradually increase tilt angle. Hip compensation — keep hips level and still, only the trunk should move. Uneven tilt angles — aim for equal range on both sides. Leaning forward or backward — tilt strictly to the side. Moving too fast — maintain slow, controlled movement.",
            "source": "kimore_guide"
        },
        {
            "text": "Lateral Trunk Tilt corrections: If your hips shift, stand against a wall to keep pelvis stable. If range is limited on one side, hold the stretch for 2-3 seconds on that side. Place one hand on your hip and slide the other down the outside of your thigh as a guide. Keep your head aligned with your spine throughout the movement.",
            "source": "kimore_guide"
        },
        {
            "text": "Lateral Trunk Tilt rehabilitation targets: Trunk lateral flexibility, core stability. Clinical focus: Lateral trunk range of motion, symmetry between left and right. Core exercise for low back pain patients — lateral trunk mobility is crucial for daily activities like reaching and bending.",
            "source": "kimore_guide"
        },
    ],
    "trunk_rotation": [
        {
            "text": "Trunk Rotation exercise: Stand upright with hands on hips. Rotate your upper body to the left, return to center, then rotate to the right. Keep hips facing forward throughout. This is KIMORE Exercise 3.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation common mistakes: Jerky movements — rotate smoothly and with control. Limited rotation range — gradually increase over sessions. Compensatory hip rotation — keep hips and feet facing forward. Moving the head independently — head should follow trunk rotation. Rushing the movement — each rotation should take 2-3 seconds.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation corrections: If your hips rotate with your trunk, sit in a chair to isolate trunk rotation. If range is limited, gently hold the end position for 1-2 seconds. Use a stick across your shoulders for feedback on rotation angle. Breathe out as you rotate to help engage core muscles.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation rehabilitation targets: Trunk rotational mobility, spinal flexibility. Clinical focus: Rotational range of motion, smoothness of movement. Important for restoring functional spinal rotation needed in walking, driving, and household activities. Contraindicated for acute disc herniation or recent spinal surgery.",
            "source": "kimore_guide"
        },
    ],
    "trunk_rotation_target": [
        {
            "text": "Trunk Rotation & Target Touching exercise (KIMORE Exercise 5): Stand upright with feet shoulder-width apart. Rotate your trunk to the left and reach your right hand to touch the target on the left side. Return to center, then rotate to the right and touch the target on the right side with your left hand. This exercise combines trunk rotation with reaching/coordination.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation & Target Touching common mistakes: Not reaching far enough — arms should extend fully to touch the target. Stepping or shifting feet — keep feet planted. Moving only the arms without rotating the trunk — the rotation should come from the spine. Rushing between targets — each rotation-reach should take 2-3 seconds. Looking down instead of toward the target.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation & Target Touching corrections: If range is limited, move targets closer initially and gradually increase distance. If balance is unstable, widen your stance or use a chair. Focus on leading with your shoulder (not just the hand) to engage proper trunk rotation. Exhale as you rotate to each target to engage core muscles. Keep the movement smooth and controlled.",
            "source": "kimore_guide"
        },
        {
            "text": "Trunk Rotation & Target Touching rehabilitation targets: Combines trunk rotational mobility with upper extremity coordination and reaching. Clinical focus: Rotational ROM, hand-eye coordination, functional reach. This exercise simulates real-world tasks like reaching for objects on shelves, driving (checking mirrors), and kitchen activities. KIMORE scoring evaluates both rotation quality and target accuracy.",
            "source": "kimore_guide"
        },
    ],
}

# =====================================================================
# KERAAL EXERCISES — Comprehensive Form Guidance
# =====================================================================

KERAAL_KNOWLEDGE = {
    "Forward Flexion": [
        {
            "text": "Forward Flexion (CTK) exercise: Stand upright with feet hip-width apart. Slowly bend forward from your hips, keeping your back straight. Reach toward your toes, feeling the stretch in your hamstrings and lower back. Return to upright slowly. This is a Keraal lower back pain rehabilitation exercise.",
            "source": "keraal_guide"
        },
        {
            "text": "Forward Flexion common mistakes: Rounding the back — the hip hinge should come from the hips, not by curving the spine. Bending the knees excessively — keep a slight knee bend but do not squat. Bouncing at the bottom — hold the stretch steadily. Looking up — keep your neck neutral, gaze follows the floor. Going too deep too fast — only bend as far as comfortable without pain.",
            "source": "keraal_guide"
        },
        {
            "text": "Forward Flexion corrections: If your back rounds, imagine pushing your hips backward like closing a car door with your butt. Place hands on your thighs and slide them down as a guide. Keep your weight on your heels, not your toes. If you feel lower back pain, reduce the range of motion. Engage your core muscles before bending to protect your spine.",
            "source": "keraal_guide"
        },
        {
            "text": "Forward Flexion rehabilitation targets: Lower back flexibility, hamstring length, hip hinge motor pattern. For low back pain patients: promotes spinal mobility, teaches proper hip hinge mechanics, and strengthens posterior chain. The hip hinge is fundamental to safe lifting and bending in daily life. Score above 27.5/50 indicates correct form.",
            "source": "keraal_guide"
        },
        {
            "text": "Forward Flexion (hip hinge) progressions: Beginners should only bend 30-45 degrees with hands on thighs. Intermediate: bend to 60-75 degrees with arms hanging. Advanced: full range touching toes. Always return to upright slowly. If pain above 3/10 occurs, reduce range immediately. Practice 10 reps x 3 sets with slow, controlled movements.",
            "source": "keraal_guide"
        },
    ],
    "Flank Stretch": [
        {
            "text": "Flank Stretch (ELK) exercise: Stand upright with feet shoulder-width apart. Raise one arm overhead and slowly stretch to the opposite side (15-25 degrees). Feel the stretch along the side of your trunk. Return to center and repeat on the other side. This is a Keraal lower back pain rehabilitation exercise.",
            "source": "keraal_guide"
        },
        {
            "text": "Flank Stretch common mistakes: Leaning forward or backward — the stretch should be purely lateral (side-to-side). Twisting the trunk — keep your chest and hips facing forward. Not raising the arm fully — the overhead arm guides the stretch. Holding breath — breathe normally throughout. Tilting too aggressively — gentle 15-25 degree tilt is sufficient.",
            "source": "keraal_guide"
        },
        {
            "text": "Flank Stretch corrections: If you twist during the stretch, perform it with your back against a wall. Place the non-stretching hand on your hip for stability. Imagine sliding your hand down the outside of your thigh on the opposite side. Keep both feet flat on the ground. If one side is tighter, hold that stretch 2 seconds longer.",
            "source": "keraal_guide"
        },
        {
            "text": "Flank Stretch rehabilitation targets: Lateral trunk flexibility, oblique muscle engagement, rib cage mobility. For low back pain: reduces lateral muscle tension, improves trunk mobility for reaching tasks, and helps correct postural asymmetries. Particularly beneficial for patients who sit for long periods. Score above 27.5/50 indicates correct form.",
            "source": "keraal_guide"
        },
        {
            "text": "Flank Stretch technique details: Inhale as you raise the arm, exhale as you bend sideways. Hold the stretch position for 1-2 seconds. Alternate sides evenly. Keep your knees slightly bent to protect the lower back. The stretch should be felt along the side ribs and waist, not in the lower back. 10 reps per side x 3 sets recommended.",
            "source": "keraal_guide"
        },
    ],
    "Torso Rotation": [
        {
            "text": "Torso Rotation (RTK) exercise: Stand with feet apart, hands on hips or arms extended at shoulder height. Rotate your trunk gently 20-30 degrees to each side. Keep your lower body stable throughout — only the upper body rotates. This is a Keraal lower back pain rehabilitation exercise.",
            "source": "keraal_guide"
        },
        {
            "text": "Torso Rotation common mistakes: Moving the hips — hips and feet must stay facing forward, only the trunk rotates. Rotating too far — excessive rotation can strain the lower back. Jerky or fast movements — rotation should be slow and smooth. Looking to the side independently — head follows the trunk naturally. Holding breath — maintain steady breathing.",
            "source": "keraal_guide"
        },
        {
            "text": "Torso Rotation corrections: If your hips rotate, sit in a chair with feet flat on the floor to isolate trunk rotation. Use a stick or towel across your shoulders to visualize the rotation angle. Squeeze your glutes to stabilize your pelvis. Move through a comfortable range — pain-free rotation only. Exhale as you rotate for better core engagement.",
            "source": "keraal_guide"
        },
        {
            "text": "Torso Rotation rehabilitation targets: Spinal rotational mobility, core stability during rotation, oblique muscle coordination. For low back pain: restores functional rotation needed for walking, driving, and household tasks. Gently mobilizes the thoracic and lumbar spine. Contraindicated for acute disc herniation. Score above 27.5/50 indicates correct form.",
            "source": "keraal_guide"
        },
        {
            "text": "Torso Rotation progressions: Begin with hands on hips and small rotations (15 degrees). Progress to arms extended at shoulder height for greater challenge. Advanced: hold a light weight or resistance band. Each rotation should take 2-3 seconds. Aim for equal range left and right. If one direction is limited, gently hold 1-2 seconds longer. 10 reps per side x 3 sets.",
            "source": "keraal_guide"
        },
    ],
}

# =====================================================================
# GENERAL REHABILITATION KNOWLEDGE
# =====================================================================

GENERAL_KNOWLEDGE = [
    {
        "exercise": "general",
        "text": "The KIMORE dataset uses a dual scoring system: Primary Outcome (PO) scores range 0-15 measuring movement quality, and Control Factor (CF) scores range 0-35 measuring physical constraints. Total score 0-50 where higher is better. Score below 25 indicates significant dysfunction. Score 25-40 indicates moderate progress. Score above 40 indicates near-normal quality.",
        "source": "kimore_scoring"
    },
    {
        "exercise": "general",
        "text": "The KERAAL scoring system evaluates exercise correctness on a 0-1 scale (multiplied by 50 for display). Correctness >= 0.55 (27.5/50) is considered CORRECT form. Below 0.55 is INCORRECT and requires feedback. The model evaluates 48-frame windows of BlazePose landmarks to assess movement quality.",
        "source": "keraal_scoring"
    },
    {
        "exercise": "general",
        "text": "Rehabilitation exercise safety guidelines: Stop any exercise if pain exceeds 5/10. Warm up for 2-3 minutes before starting. Maintain proper breathing throughout. Quality of movement is more important than quantity of repetitions. Rest 30-60 seconds between sets. Report any unusual pain or discomfort to your clinician.",
        "source": "safety_guide"
    },
    {
        "exercise": "general",
        "text": "For low back pain rehabilitation: Avoid sudden or jerky movements. Keep core muscles engaged during all exercises. Do not hold your breath. Progress gradually — increase range before increasing repetitions. Pain during exercise should stay below 3/10. Post-exercise soreness lasting more than 24 hours indicates the exercise was too intense.",
        "source": "lbp_guide"
    },
]


def populate_chromadb():
    """Load all exercise knowledge into ChromaDB for pipeline use."""
    print("=" * 60)
    print("📚 Populating ChromaDB with exercise knowledge")
    print("=" * 60)
    
    rag = RAGStore(persist_dir=RAG_DIR)
    
    docs = []
    doc_id = 0
    
    # 1) KIMORE exercises
    print("\n🏋️ Loading Kimore exercises...")
    for exercise_name, chunks in KIMORE_KNOWLEDGE.items():
        for chunk in chunks:
            docs.append({
                "id": f"kimore_{exercise_name}_{doc_id}",
                "text": chunk["text"],
                "source": chunk["source"],
                "exercise": exercise_name,
            })
            doc_id += 1
        print(f"   ✅ {exercise_name}: {len(chunks)} docs")
    
    # 2) KERAAL exercises
    print("\n🦴 Loading Keraal exercises...")
    for exercise_name, chunks in KERAAL_KNOWLEDGE.items():
        for chunk in chunks:
            # Store under display name AND under snake_case name for flexible lookup
            docs.append({
                "id": f"keraal_{exercise_name}_{doc_id}",
                "text": chunk["text"],
                "source": chunk["source"],
                "exercise": exercise_name,
            })
            doc_id += 1
            
            # Also store under snake_case key (e.g. "forward_flexion")
            snake_name = exercise_name.lower().replace(" ", "_")
            docs.append({
                "id": f"keraal_{snake_name}_{doc_id}",
                "text": chunk["text"],
                "source": chunk["source"],
                "exercise": snake_name,
            })
            doc_id += 1
        print(f"   ✅ {exercise_name}: {len(chunks)} docs (x2 for aliasing)")
    
    # 3) General knowledge
    print("\n📖 Loading general knowledge...")
    for item in GENERAL_KNOWLEDGE:
        docs.append({
            "id": f"general_{doc_id}",
            "text": item["text"],
            "source": item["source"],
            "exercise": item["exercise"],
        })
        doc_id += 1
    print(f"   ✅ {len(GENERAL_KNOWLEDGE)} general docs")
    
    # 4) Also load FAISS Keraal PDF data into ChromaDB if available
    faiss_meta_path = Path(__file__).parent / "vector_store" / "metadata.json"
    if faiss_meta_path.exists():
        import json
        with open(faiss_meta_path) as f:
            faiss_meta = json.load(f)
        
        keraal_faiss = [m for m in faiss_meta if 'keraal' in str(m.get('source', '')).lower()]
        print(f"\n📄 Loading {len(keraal_faiss)} Keraal PDF chunks from FAISS store...")
        
        for m in keraal_faiss:
            raw_exercise = m.get('exercise', '')
            # Map PDF stem names to display names
            EXERCISE_MAP = {
                'Forward_Flexion': 'Forward Flexion',
                'Flank_Stretch': 'Flank Stretch',
                'Torso_Rotation': 'Torso Rotation',
                'Torso_Rotation_2': 'Torso Rotation',
            }
            display_name = EXERCISE_MAP.get(raw_exercise, raw_exercise)
            snake_name = display_name.lower().replace(" ", "_")
            
            text = m.get('text', '').strip()
            if len(text) > 30:  # Skip tiny fragments
                docs.append({
                    "id": f"faiss_keraal_{doc_id}",
                    "text": text[:500],  # Cap length
                    "source": m.get('source', 'keraal_pdf'),
                    "exercise": display_name,
                })
                doc_id += 1
                # Also store under snake_case
                docs.append({
                    "id": f"faiss_keraal_snake_{doc_id}",
                    "text": text[:500],
                    "source": m.get('source', 'keraal_pdf'),
                    "exercise": snake_name,
                })
                doc_id += 1
        print(f"   ✅ Loaded {len(keraal_faiss)} PDF chunks (x2 for aliasing)")
    
    # Insert all into ChromaDB
    print(f"\n💾 Inserting {len(docs)} total documents into ChromaDB...")
    rag.add_docs(docs)
    
    # Verify
    count = rag._col.count()
    print(f"\n✅ ChromaDB now has {count} documents")
    
    # Test queries for each exercise
    print("\n🔍 Testing RAG retrieval...")
    test_exercises = [
        "squat", "lifting_of_arms", "lateral_trunk_tilt", "trunk_rotation", "trunk_rotation_target",
        "Forward Flexion", "Flank Stretch", "Torso Rotation",
        "forward_flexion", "flank_stretch", "torso_rotation"
    ]
    for ex in test_exercises:
        try:
            results = rag.query(query_text=f"{ex} proper form", exercise=ex, k=2)
        except Exception:
            results = None
        if results:
            print(f"   ✅ {ex}: {len(results)} results — '{results[0].text[:60]}...'")
        else:
            # Try without exercise filter
            try:
                results2 = rag.query(query_text=f"{ex} exercise technique", k=2)
            except Exception:
                results2 = None
            if results2:
                print(f"   ⚠️  {ex}: {len(results2)} results (no exercise filter) — '{results2[0].text[:60]}...'")
            else:
                print(f"   ❌ {ex}: NO RESULTS")
    
    print("\n" + "=" * 60)
    print("✅ ChromaDB population complete!")
    print("=" * 60)


if __name__ == "__main__":
    populate_chromadb()
