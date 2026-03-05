"""
Compatibility shim: makes MediaPipe 0.10.x Tasks API look like the old mp.solutions.pose API.

Usage:
    import mediapipe_compat as mp
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(...)
    results = pose.process(rgb_frame)
    for lm in results.pose_landmarks.landmark:
        lm.x, lm.y, lm.z
"""
import os
from pathlib import Path
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# Model path — relative to this file
_MODEL_PATH = str(Path(__file__).parent / "pose_landmarker_lite.task")


class _Landmark:
    """Mimics the old NormalizedLandmark with x, y, z attributes."""
    __slots__ = ("x", "y", "z", "visibility")

    def __init__(self, x: float, y: float, z: float, visibility: float = 1.0):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


class _PoseLandmarks:
    """Mimics results.pose_landmarks with a .landmark list."""
    def __init__(self, landmarks):
        self.landmark = landmarks


class _PoseResults:
    """Mimics the old Pose.process() return value."""
    def __init__(self, pose_landmarks=None):
        self.pose_landmarks = pose_landmarks


class Pose:
    """
    Drop-in replacement for mp.solutions.pose.Pose using the MediaPipe Tasks API.
    Accepts the same constructor arguments as the old API (they are ignored — the
    lite model handles detection/tracking internally).
    """

    def __init__(self, static_image_mode=False, model_complexity=1,
                 enable_segmentation=False, min_detection_confidence=0.5,
                 min_tracking_confidence=0.5, **kwargs):
        base_options = mp_python.BaseOptions(model_asset_path=_MODEL_PATH)
        running_mode = (
            vision.RunningMode.IMAGE if static_image_mode
            else vision.RunningMode.VIDEO
        )
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            num_poses=1,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._running_mode = running_mode
        self._frame_ts = 0  # millisecond timestamp for VIDEO mode

    def process(self, rgb_frame: np.ndarray) -> _PoseResults:
        """Process an RGB frame and return results compatible with old API."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        if self._running_mode == vision.RunningMode.VIDEO:
            self._frame_ts += 33  # ~30 fps
            result = self._landmarker.detect_for_video(mp_image, self._frame_ts)
        else:
            result = self._landmarker.detect(mp_image)

        if not result.pose_landmarks:
            return _PoseResults(pose_landmarks=None)

        landmarks = [
            _Landmark(lm.x, lm.y, lm.z, lm.presence)
            for lm in result.pose_landmarks[0]
        ]
        return _PoseResults(pose_landmarks=_PoseLandmarks(landmarks))

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _PoseModule:
    Pose = Pose


class _Solutions:
    pose = _PoseModule()


# Expose as mp.solutions.pose style
solutions = _Solutions()
