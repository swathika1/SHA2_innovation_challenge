# Rehab_Scorer_Coach/src/openpose_client.py

import requests
import numpy as np
from typing import Optional


class OpenPoseClient:
    def __init__(self, base_url: str = "http://127.0.0.1:9001", timeout_s: float = 2.5):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def infer(self, frame_b64: str) -> Optional[np.ndarray]:
        """
        Sends frame to OpenPose HTTP server.
        Returns:
            np.ndarray (25,4) keypoints OR None
        """

        try:
            response = requests.post(
                f"{self.base_url}/pose",
                json={"frame_b64": frame_b64},
                timeout=self.timeout_s,
            )

            if response.status_code != 200:
                print("[OPENPOSE_CLIENT] HTTP error:", response.status_code)
                return None

            data = response.json()

            if not data.get("ok", False):
                print("[OPENPOSE_CLIENT] Server error:", data.get("error"))
                return None

            keypoints = data.get("landmarks_25")

            if keypoints is None:
                print("[OPENPOSE_CLIENT] No landmarks in response")
                return None

            keypoints = np.array(keypoints, dtype=np.float32)

            if keypoints.shape != (25, 4):
                print("[OPENPOSE_CLIENT] Wrong shape:", keypoints.shape)
                return None

            return keypoints

        except Exception as e:
            print("[OPENPOSE_CLIENT] Exception:", e)
            return None