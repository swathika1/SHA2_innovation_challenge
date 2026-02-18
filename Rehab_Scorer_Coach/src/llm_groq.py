# Rehab_Scorer_Coach/src/llm_groq.py
import os
import time
from typing import List, Optional

from groq import Groq


class GroqLLM:
    """
    Text-only LLM using Groq (OpenAI-style chat completions via Groq SDK).

    Intended usage:
        - detect_exercise(pose_summary)  -> label (optional)
        - generate_feedback(exercise_name, language, rag_context, numeric_summary, pose_summary) -> list[str]
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 20,
    ):
        # Prefer env var; allow explicit override
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "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")).strip() #"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"
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not set")

        self.client = Groq(api_key=self.api_key)
        # Safe default model; override via env or arg
        self.model = (model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")).strip()
        self.timeout_seconds = int(timeout_seconds)

    # ---------------- helpers ----------------
    @staticmethod
    def _to_bullets(text: str, max_items: int = 4) -> List[str]:
        # sourcery skip: use-named-expression
        if not text:
            return []
        lines: List[str] = []
        for ln in text.splitlines():
            ln = ln.strip().lstrip("-•").strip()
            if ln:
                lines.append(ln)

        # If model replied in a paragraph, split sentences as fallback
        if not lines:
            parts = [p.strip() for p in text.replace("\n", " ").split(".") if p.strip()]
            lines = parts

        return lines[:max_items]

    def _chat(self, system: str, user: str, temperature: float, max_tokens: int):
        """
        One Groq chat completion call with basic retry.
        """
        return self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            #request_timeout=self.timeout_seconds,  # type: ignore
        )

    # ---------------- public API ----------------
    def detect_exercise(
        self,
        pose_summary: str,
        candidates: Optional[List[str]] = None,
        max_retries: int = 1,
        **kwargs,  # ignore unexpected args safely
    ) -> str:  # sourcery skip: use-next
        """
        Text-only exercise autodetection from pose summary.

        Returns one of the provided candidates, else "unknown".
        """
        if not candidates:
            candidates = [
                "lifting_of_arms",
                "lateral_trunk_tilt",
                "trunk_rotation",
                "pelvis_rotation",
                "squat",
                "unknown",
            ]

        prompt = f"""
Pick EXACTLY ONE label from this list:
{", ".join(candidates)}

Use ONLY the POSE SUMMARY below.
Return ONLY the label text. No extra words.

POSE SUMMARY:
{pose_summary}
""".strip()

        system = "You are a strict classifier. Output only one label from the list."

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = self._chat(system=system, user=prompt, temperature=0.0, max_tokens=20)
                txt = (resp.choices[0].message.content or "").strip().lower()

                # normalize: find candidate contained in output
                for c in candidates:
                    if c.lower() in txt:
                        return c

                # else: maybe model returned exactly label without containment issues
                txt_clean = txt.split()[0].strip()
                for c in candidates:
                    if txt_clean == c.lower():
                        return c

                return "unknown"
            except Exception as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))

        return f"unknown (error: {type(last_err).__name__})"

    def generate_feedback(
        self,
        exercise_name: str,
        language: str,
        rag_context: str,
        numeric_summary: str,
        pose_summary: str,
        max_retries: int = 2,
        **kwargs,  # ignore unexpected args safely (e.g., frame_b64 mistakenly passed)
    ) -> List[str]:  # sourcery skip: assign-if-exp, reintroduce-else
        """
        Generate 2-4 short actionable coaching bullets (or 1 encouragement if OK).
        Text-only. Uses: RAG context + numeric summary + pose summary.
        """
        exercise_name = (exercise_name or "unknown").strip()
        language = (language or "English").strip()

        system = (
            "You are a physiotherapy rehab coaching assistant. "
            "Follow the user instructions exactly."
        )

        user = f"""
Output language: {language}
Exercise: {exercise_name}

You will be given:
- REFERENCE (how exercise should be done)
- NUMERIC SUMMARY (score/status)
- POSE SUMMARY (key pose/angles/joints)

Rules:
- Reply with ONLY 2 to 4 short actionable bullet points.
- If form looks acceptable, reply with ONLY 1 short encouraging bullet.
- No headings, no long paragraphs, no markdown sections.
- Avoid diagnosis; focus on safe form cues.

REFERENCE (RAG):
{rag_context}

NUMERIC SUMMARY:
{numeric_summary}

POSE SUMMARY:
{pose_summary}
""".strip()

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = self._chat(system=system, user=user, temperature=0.2, max_tokens=200)
                text = (resp.choices[0].message.content or "").strip()

                bullets = self._to_bullets(text, max_items=4)

                # enforce constraints: if model returned 0 bullets, give fallback
                if not bullets:
                    return ["Keep going — form looks steady."]

                # if model returned >4, trim
                return bullets[:4]

            except Exception as e:
                last_err = e
                time.sleep(0.8 * (attempt + 1))

        return [f"LLM error: {type(last_err).__name__}: {last_err}"]