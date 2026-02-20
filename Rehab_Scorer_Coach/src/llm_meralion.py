# Rehab_Scorer_Coach/src/llm_meralion.py
import os, time, json, requests
from typing import List

class MeralionLLM:
    def __init__(self):
        #self.api_key = os.getenv("MERALION_API_KEY", "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE").strip()
        #self.base_url = os.getenv("MERALION_BASE_URL", "https://api.cr8lab.com").rstrip("/")
        self.api_key = "oyNXaKPBnylXWVMxINztmNBfEBHqVZmTpKzz2HE"
        self.base_url = "https://api.cr8lab.com/process"
        if not self.api_key or not self.base_url:
            raise RuntimeError("MERALION_API_KEY or MERALION_BASE_URL not set")

        self.headers = {
            "x-api-key": self.api_key,  # ✅ correct per guide
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: dict, timeout=30):
        url = "https://api.cr8lab.com/process" #f"{self.base_url}/chat" # f"{self.base_url}{path}"
        r = requests.post(url, headers=self.headers, json=payload, timeout=timeout)
        if r.status_code == 429:
            return r  # let caller backoff
        r.raise_for_status()
        return r

    def generate_feedback(
        self,
        language: str,
        rag_context: str,
        numeric_summary: str,
        max_retries: int = 2,
    ) -> List[str]:
        """
        MERaLiON (per your PDF) is fileKey-based:
          1) POST /upload-url
          2) PUT upload (text file)
          3) POST /process (instruction)
        Returns short bullet cues.
        """

        instruction = (
            "You are a physiotherapy rehab coach.\n"
            f"Output language: {language}\n\n"
            "Use the provided reference + numeric summary.\n"
            "Give 2-4 short actionable bullet cues.\n"
            "If posture is acceptable, return 1 encouraging line.\n"
        )

        # Put your content in the uploaded text file
        text_blob = (
            "REFERENCE (RAG):\n"
            f"{rag_context}\n\n"
            "NUMERIC SUMMARY (model/rules):\n"
            f"{numeric_summary}\n"
        )

        # 1) get upload url
        upload_req = {
            "fileName": "frame_context.txt",
            "contentType": "text/plain",
            "fileSize": len(text_blob.encode("utf-8")),
        }

        last_err = None
        for attempt in range(max_retries + 1):
            try:
                r1 = self._post("/upload-url", upload_req, timeout=30)
                if r1.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                j1 = r1.json()

                # Swagger usually returns: uploadUrl + fileKey (+ fields)
                upload_url = j1.get("uploadUrl") or j1.get("url")
                file_key = j1.get("fileKey")
                if not upload_url or not file_key:
                    raise RuntimeError(f"Unexpected /upload-url response: {j1}")

                # 2) PUT the file
                put_headers = {"Content-Type": "text/plain"}
                put = requests.put(upload_url, data=text_blob.encode("utf-8"), headers=put_headers, timeout=60)
                put.raise_for_status()

                # 3) /process using fileKey + instruction
                process_req = {
                    "fileKey": file_key,
                    "instruction": instruction,
                    # "hyperparameters": {...}  # optional
                }

                r3 = self._post("/process", process_req, timeout=60)
                if r3.status_code == 429:
                    time.sleep(1.5 * (attempt + 1))
                    continue

                out = r3.json()

                # ⚠️ adjust parsing depending on response schema
                text = (
                    out.get("result")
                    or out.get("output")
                    or out.get("text")
                    or json.dumps(out)
                )

                lines = [ln.strip("-• \n\t") for ln in str(text).split("\n") if ln.strip()]
                return lines[:4] if lines else ["Keep going — form looks steady."]

            except Exception as e:
                last_err = e

        return [f"LLM error: {type(last_err).__name__}: {last_err}"]