import os
from groq import Groq

# DO NOT hardcode keys in repo. Use env var:
# export GROQ_API_KEY="..."
client = Groq(api_key=os.environ.get("GROQ_API_KEY", "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"))
#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

SYSTEM = (
"""
You are a physiotherapy rehab coach.Look at the image and provide 3-5 short, actionable corrections. 

Task:
1) Identify the top 3-5 most likely form issues visible in this frame for this exercise.
2) Give short, actionable fixes (1 line each).
3) Keep the output as bullet points ONLY. No extra paragraphs.

Be safe and conservative: if you cannot tell, say "Camera angle unclear, please face sideways and show full body."
"""
)

def get_correction_advice_from_pose(pose_summary: str, exercise_name: str = "exercise") -> str:
    if not client.api_key:
        return "LLM disabled: GROQ_API_KEY not set."

    prompt = f"""
Exercise: {exercise_name}
Pose summary (frame): {pose_summary}

Return concise bullet points (max 5). Mention only visible form issues.
"""

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant", #"llama-3.1-70b-versatile", model="llama-3.3-70b-versatile"
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=180,
    )
    return resp.choices[0].message.content.strip()