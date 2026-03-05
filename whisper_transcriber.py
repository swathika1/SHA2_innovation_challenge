"""Whisper STT via HuggingFace InferenceClient (fal-ai provider)."""
import os
from config import HF_TOKEN

_client = None


def _get_client():
    global _client
    if _client is None:
        from huggingface_hub import InferenceClient
        _client = InferenceClient(
            provider="fal-ai",
            api_key=HF_TOKEN
        )
    return _client


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using Whisper large-v3 via HuggingFace fal-ai.

    Returns the transcribed text, or an empty string if transcription fails.
    """
    client = _get_client()
    print(f"[Whisper] Sending {len(audio_bytes)} bytes ({filename}) to Whisper large-v3")
    result = client.automatic_speech_recognition(
        audio_bytes,
        model="openai/whisper-large-v3"
    )
    print(f"[Whisper] Raw result: {result}")

    if hasattr(result, 'text'):
        return (result.text or "").strip()
    if isinstance(result, dict):
        text = result.get('text') or result.get('transcription') or result.get('output') or ""
        return text.strip()
    return str(result).strip()
