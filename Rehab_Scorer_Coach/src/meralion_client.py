import requests

BASE_URL = "https://api.cr8lab.com/process"

class MeralionClient:
    def __init__(self, api_key: str, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
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