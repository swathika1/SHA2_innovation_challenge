"""Whisper STT via Groq API (whisper-large-v3-turbo).

Uses the GROQ_API_KEY from .env — loads it lazily when needed.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv(Path(__file__).parent / ".env")

_client = None


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("❌ GROQ_API_KEY not set. Add to .env: GROQ_API_KEY=your_key")
        _client = Groq(api_key=api_key)
    return _client


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using Whisper large-v3-turbo via Groq.

    Returns the transcribed text, or an empty string if transcription fails.
    """
    try:
        client = _get_client()
    except Exception as e:
        print(f"[Whisper] Client init failed: {e}")
        return ""  # Return empty string instead of raising

    try:
        # Detect MIME type from filename extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
        mime_map = {"webm": "audio/webm", "mp4": "audio/mp4", "wav": "audio/wav",
                    "mp3": "audio/mpeg", "ogg": "audio/ogg", "m4a": "audio/mp4"}
        mime = mime_map.get(ext, "audio/webm")

        print(f"[Whisper/Groq] Sending {len(audio_bytes)} bytes ({filename}, {mime})")

        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes, mime),
            model="whisper-large-v3-turbo",
        )

        text = (transcription.text or "").strip()
        print(f"[Whisper/Groq] Result: {text!r}")
        return text
    except Exception as e:
        print(f"[Whisper] Transcription failed: {e}")
        return ""  # Return empty on error
