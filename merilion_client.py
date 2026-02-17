import requests
import httpx
from config import MERILION_USERNAME, MERILION_API_KEY, MERILION_BASE_URL

SAFETY_RULES = """Rules:
- NEVER provide a medical diagnosis
- If asked to diagnose, say: "I'm not able to diagnose conditions. Please consult your doctor."
- Be empathetic, clear, and concise
- Respond in the same language the patient uses (English, 中文, Bahasa Melayu, தமிழ்)"""


def _build_headers() -> dict:
    """Build auth headers for MERaLiON API."""
    return {
        "x-api-key": MERILION_API_KEY,
        "Content-Type": "application/json"
    }


def _build_chat_payload(messages: list, patient_context: str) -> dict:
    """Build payload for MERaLiON /chat endpoint.

    MERaLiON responds best when the full prompt is in the 'instruction' field.
    We compose instruction = patient context + conversation history + user question + safety rules.
    """
    # Extract the latest user message and conversation history
    question = ""
    history_lines = []

    for msg in messages:
        if msg["role"] == "user":
            question = msg["content"]
        elif msg["role"] == "assistant":
            history_lines.append(f"Assistant: {msg['content']}")
        elif msg["role"] == "system":
            history_lines.append(f"[Note: {msg['content']}]")

    # Build the full instruction that MERaLiON will respond to
    instruction_parts = [
        "You are a healthcare rehab assistant. Answer the patient's question directly with specific, practical advice.",
        SAFETY_RULES
    ]

    if patient_context and patient_context != "New patient - no history available.":
        instruction_parts.append(f"\nPatient Info:\n{patient_context}")

    if history_lines:
        instruction_parts.append("\nPrevious conversation:\n" + "\n".join(history_lines[-6:]))

    instruction_parts.append(f"\nPatient asks: {question}")
    instruction_parts.append("\nRespond directly to their question with helpful, specific advice:")

    return {
        "instruction": "\n".join(instruction_parts),
        "question": "answer"
    }


def _extract_response(data: dict) -> str:
    """Extract text from MERaLiON API response."""
    if "response" in data and isinstance(data["response"], dict):
        return data["response"].get("text", str(data["response"]))
    elif "response" in data:
        return str(data["response"])
    elif "choices" in data:
        return data["choices"][0]["message"]["content"]
    else:
        return str(data)


def query_merilion_sync(messages: list, patient_context: str) -> str:
    """Synchronous version for Flask routes."""
    headers = _build_headers()
    payload = _build_chat_payload(messages, patient_context)

    response = requests.post(
        f"{MERILION_BASE_URL}/chat",
        json=payload,
        headers=headers,
        timeout=30.0
    )
    response.raise_for_status()
    return _extract_response(response.json())


async def query_merilion(messages: list, patient_context: str) -> str:
    """Async version for FastAPI routes."""
    headers = _build_headers()
    payload = _build_chat_payload(messages, patient_context)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MERILION_BASE_URL}/chat",
            json=payload,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        return _extract_response(response.json())


def test_connection() -> dict:
    """Test connectivity to MERaLiON API with a real chat call."""
    headers = _build_headers()
    try:
        response = requests.post(
            f"{MERILION_BASE_URL}/chat",
            json={
                "instruction": "A patient in ACL rehab week 1 asks: My knee hurts during wall squats. What should I do instead? Give 2 alternatives.",
                "question": "answer"
            },
            headers=headers,
            timeout=15.0
        )
        return {
            "ok": response.status_code == 200,
            "status_code": response.status_code,
            "body": response.json().get("response", {}).get("text", response.text[:300])
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print(f"Testing connection to {MERILION_BASE_URL}...")
    result = test_connection()
    print(f"Status: {result}")
