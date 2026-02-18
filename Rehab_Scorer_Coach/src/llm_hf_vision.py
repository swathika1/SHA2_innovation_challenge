# Rehab_Scorer_Coach/src/llm_hf_vision.py
import os
import time
import requests
from typing import List, Optional


class HFVisionLLM:
    """
    Vision LLM via Hugging Face Router (OpenAI-compatible).
    Uses chat.completions with image inputs.

    Robustness:
      - retries for 429/5xx
      - model fallback list
      - tries image_url format first, then raw base64 "image" fallback
    """

    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self):
        self.api_key = os.getenv("HF_TOKEN", "").strip() or "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"
        self.base_url = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1").rstrip("/")

        # Fallback list (first entry can be overridden by env)
        self.models = [
            os.getenv("HF_VISION_MODEL", "").strip(),
            "zai-org/GLM-4.6V-Flash",
            "Qwen/Qwen2.5-VL-7B-Instruct",
            "Qwen/Qwen3-VL-8B-Instruct",
            "allenai/Molmo2-8B",
        ]
        self.models = [m for m in self.models if m]

        if not self.api_key:
            raise RuntimeError("HF_TOKEN not set (or hardcoded token missing)")

        # For convenience, keep a default current model (first in list)
        self.model = self.models[0] if self.models else ""

    # ---------- helpers ----------

    def _raw_b64(self, frame_dataurl_or_b64: str) -> str:
        return frame_dataurl_or_b64.split(",", 1)[1] if frame_dataurl_or_b64.startswith("data:image") else frame_dataurl_or_b64

    def _image_url(self, frame_dataurl_or_b64: str) -> str:
        return frame_dataurl_or_b64 if frame_dataurl_or_b64.startswith("data:image") else "data:image/jpeg;base64," + frame_dataurl_or_b64

    def _post_with_retries(self, url: str, headers: dict, payload: dict, timeout: int = 30, max_retries: int = 3):
        last = None
        for i in range(max_retries + 1):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=timeout)

                # Retry on rate limit / transient server errors
                if r.status_code in self.RETRY_STATUSES:
                    # Backoff a bit; longer for 429
                    sleep_s = (1.2 * (i + 1)) if r.status_code != 429 else (1.8 * (i + 1))
                    time.sleep(sleep_s)
                    last = r
                    continue

                return r
            except Exception as e:
                last = e
                time.sleep(1.2 * (i + 1))

        return last  # may be Response or Exception

    def list_models(self, limit: int = 30) -> List[str]:
        url = f"{self.base_url}/models"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()
        models = data.get("data", [])
        return [m.get("id") for m in models][:limit]

    def _parse_text(self, data: dict) -> str:
        return (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()

    def _clean_bullets(self, text: str, max_items: int = 4) -> List[str]:
        if not text:
            return ["Keep going — form looks steady."]
        lines = []
        for ln in text.splitlines():
            ln = ln.strip().lstrip("-•").strip()
            if ln:
                lines.append(ln)
        return lines[:max_items] if lines else ["Keep going — form looks steady."]

    # ---------- core ----------

    def detect_exercise(self, frame_dataurl_or_b64: str, language: str = "English") -> str:
        """
        Returns ONE label string (never a list):
          lifting_of_arms | lateral_trunk_tilt | trunk_rotation | pelvis_rotation | squat | unknown
        """
        image_url = self._image_url(frame_dataurl_or_b64)

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        system = "You are a classifier. Reply with ONLY the exercise name, nothing else."
        user_text = f"""
Identify the rehab exercise in the image. Reply with one of:
- lifting_of_arms
- lateral_trunk_tilt
- trunk_rotation
- pelvis_rotation
- squat
If unsure: unknown
Language: {language}
""".strip()

        # IMPORTANT: OpenAI-compatible image_url format:
        # {"type":"image_url","image_url":{"url":"data:image/..."}}
        base_payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]},
            ],
            "temperature": 0.0,
            "max_tokens": 30,
        }

        last_bad = None
        for m in self.models:
            payload = dict(base_payload)
            payload["model"] = m

            r = self._post_with_retries(url, headers, payload, timeout=30, max_retries=3)
            if not hasattr(r, "ok"):
                last_bad = f"{type(r).__name__}: {r}"
                continue

            if not r.ok:
                last_bad = f"HTTP {r.status_code}: {r.text[:300]}"
                continue

            data = r.json()
            txt = self._parse_text(data).splitlines()[0].strip().lower()

            # normalize
            allowed = {
                "lifting_of_arms",
                "lateral_trunk_tilt",
                "trunk_rotation",
                "pelvis_rotation",
                "squat",
                "unknown",
            }
            return txt if txt in allowed else "unknown"

        # If everything failed
        return "unknown"

    def generate_feedback(
        self,
        language: str,
        frame_dataurl_or_b64: str,
        rag_context: str,
        numeric_summary: str,
        exercise_hint: Optional[str] = None,
        max_retries: int = 2,
    ) -> List[str]:
        """
        Returns 2-4 short actionable bullet cues.
        Tries models in self.models. Uses image_url first; falls back to raw b64 image format if needed.
        """
        image_url = self._image_url(frame_dataurl_or_b64)
        raw_b64 = self._raw_b64(frame_dataurl_or_b64)

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        hint_line = f"Exercise hint (may be wrong): {exercise_hint}" if exercise_hint else ""

        system = (
            "You are a physiotherapy rehab coach. "
            "Reply with ONLY 2 to 4 short bullet points. "
            "No headings, no extra text. "
            "If form is acceptable, return 1 short encouraging bullet."
        )

        user_text = f"""
Output language: {language}

Task:
1) From the IMAGE, infer which rehab exercise the patient is doing.
2) Use the REFERENCE (RAG) + NUMERIC SUMMARY to give 2–4 short actionable coaching cues.

{hint_line}

REFERENCE (RAG):
{rag_context}

NUMERIC SUMMARY:
{numeric_summary}
""".strip()

        # Preferred payload: image_url (most compatible with HF router)
        def make_payload_image_url(model_name: str) -> dict:
            return {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            }

        # Fallback payload: raw base64 "image" (some providers support this)
        def make_payload_image_b64(model_name: str) -> dict:
            return {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image", "image": raw_b64},
                    ]},
                ],
                "temperature": 0.2,
                "max_tokens": 220,
            }

        last_err = None

        for m in self.models:
            # 1) image_url attempt
            payload = make_payload_image_url(m)
            r = self._post_with_retries(url, headers, payload, timeout=30, max_retries=max_retries)

            if hasattr(r, "ok") and r.ok:
                data = r.json()
                return self._clean_bullets(self._parse_text(data), max_items=4)

            # If we got a response but it failed, keep a short error
            if hasattr(r, "status_code"):
                last_err = f"HTTP {r.status_code}: {getattr(r, 'text', '')[:250]}"

            # 2) fallback raw b64 attempt (only if not ok / exception)
            payload2 = make_payload_image_b64(m)
            r2 = self._post_with_retries(url, headers, payload2, timeout=30, max_retries=max_retries)

            if hasattr(r2, "ok") and r2.ok:
                data = r2.json()
                return self._clean_bullets(self._parse_text(data), max_items=4)

            if hasattr(r2, "status_code"):
                last_err = f"HTTP {r2.status_code}: {getattr(r2, 'text', '')[:250]}"

        return [f"LLM error: all HF vision models failed. Last: {last_err or 'unknown'}"]