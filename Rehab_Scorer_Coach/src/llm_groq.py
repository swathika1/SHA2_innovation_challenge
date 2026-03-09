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
        # Load from .env if not already loaded
        from dotenv import load_dotenv
        load_dotenv()
        
        # Prefer explicit arg > env var > error
        self.api_key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
        if not self.api_key:
            raise RuntimeError("❌ GROQ_API_KEY not set in environment. Please ensure .env file contains: GROQ_API_KEY=your_key")

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
        Generate 2-4 short actionable coaching bullets in the specified language.
        Uses: RAG context + numeric summary + pose summary.
        """
        exercise_name = (exercise_name or "unknown").strip()
        language = (language or "English").strip()

        system = (
            "You are a physiotherapy rehab coaching assistant. "
            "Follow the user instructions exactly and ALWAYS respond in the requested language."
        )

        user = f"""Output language: {language}
Exercise: {exercise_name}

You will be given:
- REFERENCE (how exercise should be done, from medical guides - USE THIS!)
- NUMERIC SUMMARY (form score and status)
- POSE SUMMARY (body positioning details)

Rules:
- Reply with EXACTLY 2 to 4 SHORT actionable bullet points.
- If form looks acceptable, reply with ONLY 1 short encouraging bullet.
- No headings, no long paragraphs, no markdown sections.
- Avoid diagnosis; focus on safe form cues.
- Use bullet points (-, •, or *) to separate items.
- CRITICAL: Base your feedback on the REFERENCE context provided below.
- CRITICAL: Respond ENTIRELY in {language}. Do NOT mix languages under any circumstance.

REFERENCE (Medical Guide - Base your feedback on this):
{rag_context if rag_context.strip() else "Standard rehabilitation form guidance for " + exercise_name}

NUMERIC SUMMARY:
{numeric_summary}

POSE SUMMARY:
{pose_summary}

FINAL INSTRUCTION: You MUST respond in {language} only. Use the REFERENCE context above to provide specific, exercise-appropriate feedback. Be actionable and clear.""".strip()

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                resp = self._chat(system=system, user=user, temperature=0.2, max_tokens=250)
                text = (resp.choices[0].message.content or "").strip()
                print(f"[LLM] Raw response ({language}): {text[:100]}...")
                
                # Parse bullet points
                lines = text.split('\n')
                feedback = []
                for line in lines:
                    line = line.strip()
                    # Remove bullet markers
                    if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                        line = line[1:].strip()
                    if line and len(line) > 10:  # Skip short lines
                        feedback.append(line)
                
                if feedback:
                    print(f"[LLM] Parsed {len(feedback)} feedback items in {language}")
                    return feedback[:4]  # Return up to 4 items
                
                # Fallback if no bullet points found
                print(f"[LLM] No bullets found, returning raw text")
                return [text] if text else ["Continue with proper form."]
            
            except Exception as e:
                last_err = e
                print(f"[LLM] Attempt {attempt + 1} failed: {e}")
                time.sleep(0.6 * (attempt + 1))

        print(f"[LLM] Failed after {max_retries + 1} attempts")
        return [f"Continue with proper form. ({language} feedback unavailable)"]

    # ============================================================================
    # Helper: Convert text output to bullet points
    # ============================================================================