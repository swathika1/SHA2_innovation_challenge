RISK_SIGNALS = {
    "high": {
        "en": ["chest pain", "can't breathe", "shortness of breath", "severe pain",
                "fainting", "numbness", "heart", "suicidal", "bleeding"],
        "zh": ["胸痛", "呼吸困难", "严重疼痛", "晕厥", "麻木", "心脏", "出血"],
        "ms": ["sakit dada", "susah bernafas", "sakit teruk", "pengsan", "kebas", "jantung"],
        "ta": ["மார்பு வலி", "மூச்சுத் திணறல்", "கடுமையான வலி", "மயக்கம்"]
    },
    "medium": {
        "en": ["pain", "hurts", "discomfort", "swelling", "dizziness", "nausea",
                "not sleeping", "fever", "worse"],
        "zh": ["疼痛", "不舒服", "肿胀", "头晕", "恶心", "发烧", "更严重"],
        "ms": ["sakit", "tidak selesa", "bengkak", "pening", "mual", "demam"],
        "ta": ["வலி", "வீக்கம்", "தலைசுற்றல்", "குமட்டல்", "காய்ச்சல்"]
    }
}

REFERRAL_THRESHOLD = 7.0

REFERRAL_MESSAGES = {
    "en": "⚠️ Based on what you've shared, I'd strongly recommend speaking with a healthcare professional soon. Please contact your doctor or visit a clinic.",
    "zh": "⚠️ 根据您所描述的情况，我强烈建议您尽快咨询医疗专业人员。请联系您的医生或前往诊所。",
    "ms": "⚠️ Berdasarkan apa yang anda kongsikan, saya sangat mengesyorkan anda berjumpa dengan profesional kesihatan secepat mungkin. Sila hubungi doktor anda.",
    "ta": "⚠️ நீங்கள் பகிர்ந்தவற்றின் அடிப்படையில், நான் உங்களுக்கு விரைவில் ஒரு மருத்துவ நிபுணரிடம் பேசுமாறு பரிந்துரைக்கிறேன்."
}


def calculate_risk_score(message: str, detected_lang: str, session_history: list) -> dict:
    score = 0.0
    triggered = []

    for phrase in RISK_SIGNALS["high"].get(detected_lang, RISK_SIGNALS["high"]["en"]):
        if phrase.lower() in message.lower():
            score += 4.0
            triggered.append(phrase)

    for phrase in RISK_SIGNALS["medium"].get(detected_lang, RISK_SIGNALS["medium"]["en"]):
        if phrase.lower() in message.lower():
            score += 2.0
            triggered.append(phrase)

    recent_pain_count = sum(1 for s in session_history if s.pain_reported and s.pain_reported != "none")
    score += recent_pain_count * 1.5

    score = min(score, 10.0)

    return {
        "score": round(score, 1),
        "should_refer": score >= REFERRAL_THRESHOLD,
        "triggers": triggered
    }
