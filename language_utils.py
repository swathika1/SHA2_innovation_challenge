"""Utilities for Jimmy's supported language detection and normalization."""

from __future__ import annotations

import re

try:
    from langdetect import DetectorFactory, detect as _detect_language

    DetectorFactory.seed = 0
except Exception:
    _detect_language = None


DEFAULT_JIMMY_LANGUAGE = "English"
SUPPORTED_JIMMY_LANGUAGES = (
    "English",
    "Chinese",
    "Malay",
    "Tamil",
    "Singlish",
)

_LANGUAGE_ALIASES = {
    "en": "English",
    "en-gb": "English",
    "en-sg": "English",
    "en-us": "English",
    "english": "English",
    "zh": "Chinese",
    "zh-cn": "Chinese",
    "zh-hans": "Chinese",
    "zh-sg": "Chinese",
    "chinese": "Chinese",
    "中文": "Chinese",
    "ms": "Malay",
    "ms-my": "Malay",
    "id": "Malay",
    "indonesian": "Malay",
    "malay": "Malay",
    "bahasa melayu": "Malay",
    "ta": "Tamil",
    "ta-in": "Tamil",
    "tamil": "Tamil",
    "singlish": "Singlish",
}

_CHINESE_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_MALAY_RE = re.compile(
    r"\b("
    r"saya|awak|anda|boleh|tak|tidak|latihan|senaman|"
    r"sakit|bagaimana|apa|terima\s+kasih|hari\s+ini|"
    r"perlu|mahu|rasa|sedikit|dengan|untuk|bantu|tolong"
    r")\b",
    re.IGNORECASE,
)
_SINGLISH_RE = re.compile(
    r"\b("
    r"lah|lor|leh|meh|sia|shiok|alamak|walao|"
    r"can\s+or\s+not|cannot\s+lah|can\s+lah"
    r")\b",
    re.IGNORECASE,
)


def normalize_supported_language(value: str | None, default: str = DEFAULT_JIMMY_LANGUAGE) -> str:
    """Map language names/codes to Jimmy's supported language set."""
    if not value:
        return default

    cleaned = value.strip()
    if not cleaned:
        return default

    if cleaned in SUPPORTED_JIMMY_LANGUAGES:
        return cleaned

    return _LANGUAGE_ALIASES.get(cleaned.lower(), default)


def detect_supported_language(text: str | None, hint: str | None = None) -> str:
    """Detect the closest supported Jimmy language from user text."""
    normalized_hint = normalize_supported_language(hint, default="")
    cleaned = (text or "").strip()
    if not cleaned:
        return normalized_hint or DEFAULT_JIMMY_LANGUAGE

    if _TAMIL_RE.search(cleaned):
        return "Tamil"

    if _CHINESE_RE.search(cleaned):
        return "Chinese"

    if len(_MALAY_RE.findall(cleaned)) >= 2:
        return "Malay"

    if _SINGLISH_RE.search(cleaned) and _LATIN_RE.search(cleaned):
        return "Singlish"

    latin_only = re.sub(r"[^A-Za-z]", "", cleaned)
    if len(latin_only) < 4:
        return normalized_hint or DEFAULT_JIMMY_LANGUAGE

    if _detect_language is None:
        return normalized_hint or DEFAULT_JIMMY_LANGUAGE

    try:
        detected = _detect_language(cleaned)
    except Exception:
        return normalized_hint or DEFAULT_JIMMY_LANGUAGE

    normalized = normalize_supported_language(detected, default="")
    if normalized:
        if normalized == "English" and normalized_hint == "Singlish":
            return "Singlish"
        return normalized

    return normalized_hint or DEFAULT_JIMMY_LANGUAGE
