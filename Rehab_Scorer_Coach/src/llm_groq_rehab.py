import os, time, json, base64, requests
from typing import List, Optional

class GroqRehabLLM:
    """
    Groq chat model wrapper.
    - detect_exercise(frame_b64) -> one of: arms_lift, lateral_trunk_tilt, trunk_rotation, pelvis_rotation, squat, unknown
    - generate_feedback(...) -> list[str]
    """

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "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")
        self.base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set in env")

    def _post_chat(self, messages, temperature=0.2, max_tokens=256):
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def _strip_dataurl(self, frame_b64: str) -> str:
        # accepts raw base64 OR dataURL
        if not frame_b64:
            return ""
        return frame_b64.split(",", 1)[1] if frame_b64.startswith("data:image") else frame_b64

    def detect_exercise(self, frame_b64: str, max_retries: int = 1) -> str:
        """
        Uses the LLM to classify the exercise from a single frame.
        NOTE: This only works if your chosen Groq model supports image inputs.
        If it doesn't, return 'unknown' and fallback to other logic.
        """
        raw_b64 = self._strip_dataurl(frame_b64)
        if not raw_b64:
            return "unknown"

        # KiMoRe exercise label set (your canonical IDs)
        allowed = [
            "arms_lift",
            "lateral_trunk_tilt",
            "trunk_rotation",
            "pelvis_rotation",
            "squat",
            "unknown",
        ]

        prompt = f"""
You are a physiotherapy assistant.
Classify which KiMoRe rehab exercise is being performed in the IMAGE.

Pick exactly ONE label from:
{allowed}

Return ONLY a JSON object like:
{{"exercise": "<one_label_from_list>"}}
""".strip()

        # ⚠️ Groq supports OpenAI-style chat; image support depends on model.
        # If your model doesn't support images, this will error -> we return 'unknown'.
        messages = [
            {"role": "system", "content": "You output strict JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"}},
                ],
            },
        ]

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                data = self._post_chat(messages, temperature=0.0, max_tokens=120)
                text = data["choices"][0]["message"]["content"].strip()

                # Parse JSON safely
                obj = json.loads(text)
                ex = (obj.get("exercise") or "unknown").strip().lower()

                # normalize a bit
                aliases = {
                    "lifting_of_the_arms": "arms_lift",
                    "arms": "arms_lift",
                    "arm_lift": "arms_lift",
                    "lateral_tilt": "lateral_trunk_tilt",
                    "lateral_tilt_of_trunk": "lateral_trunk_tilt",
                    "trunk_tilt": "lateral_trunk_tilt",
                    "rotation": "trunk_rotation",
                    "pelvis_rotations": "pelvis_rotation",
                    "pelvic_rotation": "pelvis_rotation",
                    "squatting": "squat",
                }
                ex = aliases.get(ex, ex)

                return ex if ex in allowed else "unknown"

            except Exception as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))

        # image unsupported or bad response
        return "unknown"

    def generate_feedback(
        self,
        exercise_name: str,
        language: str,
        rag_context: str,
        numeric_summary: str,
        pose_summary: Optional[str] = None,
        max_retries: int = 1,
    ) -> List[str]:
        """
        Groq text-only feedback generator (safe).
        If your Groq model supports image input and you want it, add frame_b64 here too.
        """
        # Make the model stop printing headers like "**REFERENCE**"
        prompt = f"""
You are a physiotherapy rehab coach.

Output language: {language}
Exercise: {exercise_name}

Use ONLY the reference and summaries below to give 2–4 short actionable cues.
Do NOT print headings like "REFERENCE" or "NUMERIC SUMMARY".
Return only bullet points.

REFERENCE:
{rag_context}

NUMERIC SUMMARY:
{numeric_summary}

POSE SUMMARY:
{pose_summary or ""}
""".strip()

        messages = [
            {"role": "system", "content": "Be concise. Output only bullet points."},
            {"role": "user", "content": prompt},
        ]

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                data = self._post_chat(messages, temperature=0.2, max_tokens=220)
                text = data["choices"][0]["message"]["content"].strip()

                lines = []
                for ln in text.splitlines():
                    ln = ln.strip().lstrip("-•").strip()
                    if ln:
                        lines.append(ln)

                return lines[:4] if lines else ["Keep going — form looks steady."]

            except Exception as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))

        return [f"LLM error: {type(last_err).__name__}: {last_err}"]
