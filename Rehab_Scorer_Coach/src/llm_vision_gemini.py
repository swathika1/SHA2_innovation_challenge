#from __future__ import annotations
import base64
import cv2
import numpy as np
import os
# NEW SDK (recommended)
from google import genai
from typing import Optional
from PIL import Image

#from google import genai

# Google Gemini SDK
#import google.generativeai as genai

# Env var: GEMINI_API_KEY
#genai.configure(api_key="AIzaSyC4ybW5p-fhTY2LJ32Jgok-ELz4-oF7IkA")

old_code = """
# Choose a multimodal model. "gemini-1.5-flash" is usually fast & good for demos.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
model = genai.GenerativeModel(MODEL_NAME)

def frame_to_jpeg_bytes(bgr_frame: np.ndarray, jpeg_quality: int = 85) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", bgr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    )
    if not ok:
        raise ValueError("Failed to encode frame as JPEG")
    return buf.tobytes()

def get_correction_advice_from_vision_llm(
    bgr_frame: np.ndarray,
    exercise_name: str = "exercise",
    max_words: int = 50
) -> str:
    
    #Vision -> Text coaching using Gemini.
    #Returns short, safe, actionable advice.
    img_bytes = frame_to_jpeg_bytes(bgr_frame)

    prompt = (
        f"You are a physiotherapy coach. The image shows someone doing: {exercise_name}.\n"
        f"Give 3 bullet points to correct form safely (<= {max_words} words total).\n"
        "Be specific about posture/alignment (back, knees, hips, shoulders), range of motion, and speed.\n"
        "No diagnosis. If unclear, say one sentence: 'Please adjust the camera/lighting'."
    )

    # Gemini expects image bytes as a "Part"
    response = model.generate_content(
        [
            prompt,
            {"mime_type": "image/jpeg", "data": img_bytes},
        ],
        generation_config={
            "temperature": 0.4,
            "max_output_tokens": 160,
        }
    )

    text = (response.text or "").strip()
    return text[:700]


# Rehab_Scorer_Coach/src/llm_vision_gemini.py
# requires: pip install -U google-genai


# ⚠️ Do NOT commit real key into GitHub.
# Use env var GEMINI_API_KEY or put a placeholder here for local demo.
GEMINI_API_KEY = "AIzaSyC4ybW5p-fhTY2LJ32Jgok-ELz4-oF7IkA" # os.getenv("GEMINI_API_KEY", "PASTE_YOUR_KEY_HERE")

# Pick a working model per Google docs/quickstart.
# If this ever changes, update here only.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # :contentReference[oaicite:1]{index=1}


def _bgr_to_jpeg_bytes(bgr, quality=85) -> bytes:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
# sourcery skip: swap-if-expression
    return b"" if not ok else buf.tobytes()


def get_correction_advice_from_vision_llm(bgr_image, exercise_name="exercise") -> str:
    # sourcery skip: extract-method, reintroduce-else, swap-if-else-branches, use-named-expression
    
    #Input: BGR image (np array)
    #Output: text advice (string). Never returns empty.
    if not GEMINI_API_KEY or GEMINI_API_KEY == "PASTE_YOUR_KEY_HERE":
        return "Set GEMINI_API_KEY to enable AI feedback."

    img_bytes = _bgr_to_jpeg_bytes(bgr_image)
    if not img_bytes:
        return "Could not encode frame. Please try again."

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = (
            f"You are a physiotherapy coach. The user is doing: {exercise_name}. "
            "Look at the image and provide 3-5 short, actionable corrections. "
            "Be specific (posture, joint alignment, range of motion, speed). "
            "Output as bullet points only."
        )

        # google-genai accepts bytes directly as an image part
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                {"mime_type": "image/jpeg", "data": img_bytes},
            ],
        )

        text = (resp.text or "").strip()
        if not text:
            return "Try: keep your torso upright, slow down, and keep joints aligned."
        return text

    except Exception as e:
        # IMPORTANT: surface the error so you know what’s wrong
        return f"LLM error: {type(e).__name__}: {e}"
"""

# Rehab_Scorer_Coach/src/llm_vision_gemini.py



# ✅ You asked to set API key explicitly.
# Put your real key here (NOT recommended for GitHub), or set env var GEMINI_API_KEY.
GEMINI_API_KEY = "AIzaSyAwwb_jmpc9HpJZivAc4EmBtOjCHQOQC_Q" #"AIzaSyC4ybW5p-fhTY2LJ32Jgok-ELz4-oF7IkA"


def _get_client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not key or "PASTE_YOUR_GEMINI_API_KEY_HERE" in key:
        raise RuntimeError(
            "Gemini API key missing. Set env var GEMINI_API_KEY or edit GEMINI_API_KEY in llm_vision_gemini.py"
        )
    return genai.Client(api_key=key)


def _bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    """OpenCV BGR -> PIL RGB image"""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def get_correction_advice_from_vision_llm(
    bgr_frame: np.ndarray,
    exercise_name: str = "exercise",
    score: Optional[float] = None,
) -> str:
    """
    Returns short coaching feedback for the frame.
    """
    client = _get_client()

    img = _bgr_to_pil(bgr_frame)

    score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "unknown"
    prompt = f"""
You are a physiotherapy rehab coach.Look at the image and provide 3-5 short, actionable corrections. 

Exercise: {exercise_name}
Frame score (0-50): {score_txt}

Task:
1) Identify the top 3-5 most likely form issues visible in this frame for this exercise.
2) Give short, actionable fixes (1 line each).
3) Keep the output as bullet points ONLY. No extra paragraphs.

Be safe and conservative: if you cannot tell, say "Camera angle unclear, please face sideways and show full body."
""".strip()

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, img],
        )
        return (resp.text or "").strip()
    except Exception as e:
        # Never crash your live loop because Gemini failed
        return f"LLM error: {type(e).__name__}: {e}"
