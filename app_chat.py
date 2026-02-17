from fastapi import FastAPI
from pydantic import BaseModel
from langdetect import detect
from merilion_client import query_merilion
from risk_engine import calculate_risk_score, REFERRAL_MESSAGES
from session_manager import get_patient_context, Session, SessionLog, PatientProfile
from exercise_advisor import get_exercise_modification
import uuid
from datetime import datetime

app = FastAPI(title="Rehab Coach - MeriLion Chat API")


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    conversation_history: list  # [{"role": "user/assistant", "content": "..."}]


@app.post("/chat")
async def chat(req: ChatRequest):
    # 1. Detect language
    try:
        lang = detect(req.message)
        lang = lang if lang in ["en", "zh-cn", "ms", "ta"] else "en"
        lang_key = "zh" if "zh" in lang else lang
    except Exception:
        lang_key = "en"

    # 2. Load patient context
    patient_context = get_patient_context(req.patient_id)

    # 3. Load recent sessions for risk scoring
    db = Session()
    recent_sessions = (
        db.query(SessionLog)
        .filter_by(patient_id=req.patient_id)
        .order_by(SessionLog.timestamp.desc())
        .limit(3)
        .all()
    )
    patient = db.query(PatientProfile).filter_by(patient_id=req.patient_id).first()

    # 4. Calculate risk score
    risk = calculate_risk_score(req.message, lang_key, recent_sessions)

    # 5. If high risk — return referral message immediately
    if risk["should_refer"]:
        referral_msg = REFERRAL_MESSAGES.get(lang_key, REFERRAL_MESSAGES["en"])
        log_session(db, req.patient_id, req.message, risk["score"], pain=", ".join(risk["triggers"]))
        db.close()
        return {"response": referral_msg, "risk_score": risk["score"], "referred": True}

    # 6. Check for pain + exercise modification request
    pain_keywords = ["pain", "hurts", "sore", "ache", "sakit", "疼", "வலி"]
    exercise_keywords = ["exercise", "workout", "training", "latihan", "运动", "உடற்பயிற்சி"]
    message_lower = req.message.lower()

    if any(p in message_lower for p in pain_keywords) and any(e in message_lower for e in exercise_keywords):
        pain_area = extract_pain_area(req.message)
        current_plan = patient.exercise_plan if patient else "general fitness plan"
        modification = get_exercise_modification(pain_area, current_plan)
        req.conversation_history.append({"role": "system", "content": f"Exercise context: {modification}"})

    # 7. Query MeriLion
    response_text = await query_merilion(
        req.conversation_history + [{"role": "user", "content": req.message}],
        patient_context
    )

    # 8. Log the session
    log_session(db, req.patient_id, req.message, risk["score"], pain=", ".join(risk["triggers"]) or "none")
    db.close()

    return {
        "response": response_text,
        "risk_score": risk["score"],
        "referred": False,
        "language": lang_key
    }


def extract_pain_area(message: str) -> str:
    body_parts = ["knee", "back", "shoulder", "ankle", "hip", "neck", "wrist", "elbow"]
    for part in body_parts:
        if part in message.lower():
            return part
    return "general"


def log_session(db, patient_id, message, score, pain):
    log = SessionLog(
        id=str(uuid.uuid4()),
        patient_id=patient_id,
        timestamp=datetime.utcnow(),
        summary=message[:200],
        pain_reported=pain,
        risk_score=score
    )
    db.add(log)
    db.commit()
