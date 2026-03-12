import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = "https://api.cr8lab.com/process"

class MeralionClient:
    def __init__(self, api_key: str = None, timeout: int = 60):
        # Load from environment if not provided
        self.api_key = api_key or os.environ.get("MERILION_API_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("MERILION_API_KEY not set in environment or provided")

    def _headers(self):
        # Use x-api-key header (correct authentication method)
        return {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }

    def summarize(self, text: str) -> str:
        """
        Text-only. We will pass: RAG context + pose-derived notes + language instruction inside text.
        """
        url = f"{BASE_URL}/summarize"
        payload = {"text": text}
        r = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        # Depending on API shape; keep robust:
        return data.get("summary") or data.get("text") or str(data)

    def transcribe(self, audio_file_path: str) -> str:
        """
        If you later record audio check-ins, use this.
        """
        url = f"{BASE_URL}/transcribe"
        with open(audio_file_path, "rb") as f:
            files = {"file": f}
            r = requests.post(url, files=files, headers=self._headers(), timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("transcript") or data.get("text") or str(data)