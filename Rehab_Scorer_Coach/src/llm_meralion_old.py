# Rehab_Scorer_Coach/src/llm_meralion.py
import os, time, requests
from typing import List, Optional

class MeralionLLM:
    def __init__(self):
        self.api_key = "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE"
        self.base_url = "https://api.cr8lab.com"
        if not self.api_key or not self.base_url:
            raise RuntimeError("MERALION_API_KEY or MERALION_BASE_URL not set in env")

    def generate_feedback(
        self,
        exercise_name: str,
        language: str,
        frame_b64: str,
        rag_context: str,
        numeric_summary: str,
        max_retries: int = 2,
    ) -> List[str]:
        """
        Returns a list of short feedback bullets.
        """
        # ✅ Replace this endpoint with the one in your onboarding PDF
        url = f"{self.base_url}/generate"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
# Exercise: {exercise_name}
        prompt = f"""
You are a physiotherapy rehab coach.
Excercise : Autodetect the Excercise and find what excercise the patient is performing from the image provided.
Output language: {language}

Use the IMAGE (patient frame) + the provided exercise reference + numeric summary.
Give 2-4 short actionable bullet cues.
If posture is acceptable, return 1 encouraging line.

REFERENCE (RAG):
{rag_context}

NUMERIC SUMMARY (model/rules):
{numeric_summary}
""".strip()

        payload = {
            "input": {
                "text": prompt,
                "image_base64": frame_b64,     # <— depends on API spec; rename accordingly
            }
        }

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=15)
                if r.status_code == 429:
                    # simple backoff
                    time.sleep(1.5 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = r.json()

                # ✅ Adapt this parsing to the API response format
                text = data.get("output", {}).get("text", "") or data.get("text", "")
                lines = [ln.strip("-• \n\t") for ln in text.split("\n") if ln.strip()]
                # keep it short
                return lines[:4] if lines else ["Keep going — form looks steady."]

            except Exception as e:
                last_err = e

        return [f"LLM error: {type(last_err).__name__}: {last_err}"]