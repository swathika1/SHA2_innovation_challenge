PAIN_MODIFICATIONS = {
    "knee": "Avoid squats and lunges. Replace with seated leg raises and water-based exercises.",
    "back": "Pause any deadlifts or heavy lifting. Focus on gentle stretching and core breathing.",
    "shoulder": "Stop overhead movements. Try pendulum swings and gentle resistance band work.",
    "ankle": "Avoid weight-bearing exercises. Switch to upper body and seated exercises only.",
    "general": "Reduce overall intensity by 50%. Prioritise rest and light stretching."
}


def get_exercise_modification(pain_area: str, current_plan: str) -> str:
    area = pain_area.lower()
    for key in PAIN_MODIFICATIONS:
        if key in area:
            advice = PAIN_MODIFICATIONS[key]
            return f"Based on your current plan ({current_plan}), here's what I'd suggest modifying: {advice}"
    return f"Since you're feeling discomfort, I recommend reducing the intensity of your current plan: {current_plan}. {PAIN_MODIFICATIONS['general']}"
