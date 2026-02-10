import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class PoseExtractor:
    """
    MediaPipe Pose Landmarker (Tasks API).
    Input: BGR frame (np.ndarray)
    Output: list of 33 landmarks (NormalizedLandmark) or None
    """
    def __init__(self, model_asset_path: str):
        base_options = python.BaseOptions(model_asset_path=model_asset_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)
        self._closed = False
        
    def detect_landmarks(self, bgr_frame: np.ndarray):
        if bgr_frame is None:
            return None
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.detector.detect(mp_image)

        return result.pose_landmarks[0] if result.pose_landmarks else None
        
    def close(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        try:
            if getattr(self, "detector", None) is not None:
                self.detector.close()
        except Exception:
            pass
        finally:
            self.detector = None

    def __del__(self):  # sourcery skip: use-contextlib-suppress
        # avoid noisy shutdown errors
        try:
            self.close()
        except Exception:
            pass