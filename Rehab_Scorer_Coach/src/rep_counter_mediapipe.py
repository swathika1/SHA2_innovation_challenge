"""
MediaPipe Angle-Based Rep Counter for Rehabilitation Exercises
Proven approach from sports-science / AI-fitness literature:
  1. Calculate joint angles from MediaPipe 33-point landmarks
  2. Smooth with Exponential Moving Average (EMA)
  3. Two-threshold state machine with hysteresis
  4. Minimum rep duration to prevent false counting

Supports:  Kimore  -> squat, lifting_of_arms, lateral_trunk_tilt, trunk_rotation
           Keraal  -> forward_flexion, flank_stretch, torso_rotation
"""

import numpy as np
import time
from typing import Dict, Optional


# MediaPipe BlazePose landmark indices
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28
NOSE = 0


# Exercise profile definitions
# direction = "down" means angle decreases to reach peak (e.g. squat, flexion)
# direction = "up"   means angle increases to reach peak (e.g. arm raise)
EXERCISE_PROFILES = {
    # --- Kimore exercises ---
    # NOTE: Thresholds relaxed so EMA-smoothed values (alpha=0.35) can
    #       reach them during normal-range-of-motion reps.
    "squat": {
        "joints": [
            ("L", L_HIP, L_KNEE, L_ANKLE),
            ("R", R_HIP, R_KNEE, R_ANKLE),
        ],
        "rest_threshold": 150,   # Standing: knee angle > 150 deg
        "peak_threshold": 135,   # Squatting: knee angle < 135 deg
        "direction": "down",
        "min_rep_sec": 1.0,
    },
    "lifting_of_arms": {
        "joints": [
            ("L", L_HIP, L_SHOULDER, L_ELBOW),
            ("R", R_HIP, R_SHOULDER, R_ELBOW),
        ],
        "rest_threshold": 45,    # Arms at sides: angle < 45 deg
        "peak_threshold": 60,    # Arms raised: angle > 60 deg
        "direction": "up",
        "min_rep_sec": 1.0,
    },
    "lateral_trunk_tilt": {
        "joints": [
            ("L", L_SHOULDER, L_HIP, L_KNEE),
            ("R", R_SHOULDER, R_HIP, R_KNEE),
        ],
        "rest_threshold": 162,   # Standing straight: ~170 deg
        "peak_threshold": 155,   # Tilted: < 155 deg
        "direction": "down",
        "min_rep_sec": 0.8,
        "use_min": True,
    },
    "trunk_rotation": {
        "joints": "rotation",    # Special: shoulder-width / hip-width ratio
        "rest_threshold": 0.85,
        "peak_threshold": 0.65,
        "direction": "down",
        "min_rep_sec": 1.0,
    },
    # --- Keraal exercises ---
    "forward_flexion": {
        "joints": [
            ("L", L_SHOULDER, L_HIP, L_KNEE),
            ("R", R_SHOULDER, R_HIP, R_KNEE),
        ],
        "rest_threshold": 155,
        "peak_threshold": 110,
        "direction": "down",
        "min_rep_sec": 1.5,
    },
    "flank_stretch": {
        "joints": [
            ("L", L_SHOULDER, L_HIP, L_KNEE),
            ("R", R_SHOULDER, R_HIP, R_KNEE),
        ],
        "rest_threshold": 165,
        "peak_threshold": 150,
        "direction": "down",
        "min_rep_sec": 1.2,
        "use_min": True,
    },
    "torso_rotation": {
        "joints": "rotation",
        "rest_threshold": 0.80,
        "peak_threshold": 0.55,
        "direction": "down",
        "min_rep_sec": 1.0,
    },
    "trunk_rotation_target": {
        "joints": "rotation",
        "rest_threshold": 0.85,
        "peak_threshold": 0.60,
        "direction": "down",
        "min_rep_sec": 1.0,
    },
    "pelvis_rotation": {
        "joints": "rotation",
        "rest_threshold": 0.85,
        "peak_threshold": 0.65,
        "direction": "down",
        "min_rep_sec": 1.0,
    },
}

# Map exercise display names to profile keys
EXERCISE_NAME_MAP = {
    "squat": "squat",
    "lifting of arms": "lifting_of_arms",
    "lifting_of_arms": "lifting_of_arms",
    "lateral trunk tilt": "lateral_trunk_tilt",
    "lateral_trunk_tilt": "lateral_trunk_tilt",
    "trunk rotation": "trunk_rotation",
    "trunk_rotation": "trunk_rotation",
    "forward flexion": "forward_flexion",
    "forward_flexion": "forward_flexion",
    "flank stretch": "flank_stretch",
    "flank_stretch": "flank_stretch",
    "torso rotation": "torso_rotation",
    "torso_rotation": "torso_rotation",
    "pelvis rotation": "pelvis_rotation",
    "pelvis_rotation": "pelvis_rotation",
    "trunk_rotation_target": "trunk_rotation_target",
    "trunk rotation target": "trunk_rotation_target",
    "trunk rotation and target": "trunk_rotation_target",
    # Keraal class codes
    "ctk": "forward_flexion",
    "elk": "flank_stretch",
    "rtk": "torso_rotation",
}


def _angle_3pt(p1, p2, p3):
    """Angle at p2 formed by p1->p2->p3, in degrees [0, 180]."""
    v1 = p1[:2] - p2[:2]
    v2 = p3[:2] - p2[:2]
    m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if m1 < 1e-6 or m2 < 1e-6:
        return 0.0
    cos_a = np.clip(np.dot(v1, v2) / (m1 * m2), -1, 1)
    return float(np.degrees(np.arccos(cos_a)))


def _shoulder_hip_ratio(landmarks):
    """Ratio of shoulder width to hip width - drops when torso rotates."""
    sw = abs(landmarks[L_SHOULDER][0] - landmarks[R_SHOULDER][0])
    hw = abs(landmarks[L_HIP][0] - landmarks[R_HIP][0])
    if hw < 1e-6:
        return 1.0
    return float(sw / hw)


class RepCounterMediaPipe:
    """
    Angle-based rep counter with EMA smoothing and hysteresis.

    Usage:
        counter = RepCounterMediaPipe()
        for each frame:
            rep_done = counter.process(landmarks_33x3, "squat")
    """

    EMA_ALPHA = 0.35  # Smoothing factor (lower = smoother, slower response)

    def __init__(self):
        self._smoothed_value = None   # EMA-smoothed angle/ratio
        self._state = "rest"          # "rest" or "peak"
        self._last_rep_time = 0       # Timestamp of last rep
        self._current_exercise = ""
        self.rep_count = 0            # Kept for backward compat

    # -- public API --

    def process(self, landmarks, exercise_name):
        """
        Process one frame. Returns True if a rep was just completed.
        landmarks: (33, 3) or (33, 4) - MediaPipe pose, values in [0,1].
        """
        if landmarks is None or len(landmarks) < 33:
            return False

        # Normalise pixel coords to [0,1] if needed
        lm = landmarks.copy().astype(float)
        if lm[:, :2].max() > 1.5:
            lm[:, 0] /= 640
            lm[:, 1] /= 480

        # Resolve exercise name to profile
        key = self._resolve_exercise(exercise_name)
        if key is None:
            return False

        # Reset EMA if exercise changed
        if key != self._current_exercise:
            self._smoothed_value = None
            self._state = "rest"
            self._current_exercise = key

        profile = EXERCISE_PROFILES[key]

        # Compute raw metric for this frame
        raw = self._compute_metric(lm, profile)
        if raw is None:
            return False

        # EMA smoothing
        if self._smoothed_value is None:
            self._smoothed_value = raw
        else:
            self._smoothed_value = (
                self.EMA_ALPHA * raw + (1 - self.EMA_ALPHA) * self._smoothed_value
            )
        val = self._smoothed_value

        # State machine with hysteresis
        direction = profile["direction"]
        rest_th = profile["rest_threshold"]
        peak_th = profile["peak_threshold"]
        min_sec = profile.get("min_rep_sec", 1.0)

        rep_completed = False

        if direction == "down":
            # Angle decreases toward peak
            if self._state == "rest" and val < peak_th:
                self._state = "peak"
            elif self._state == "peak" and val > rest_th:
                now = time.time()
                if now - self._last_rep_time >= min_sec:
                    rep_completed = True
                    self._last_rep_time = now
                self._state = "rest"
        else:  # direction == "up"
            # Angle increases toward peak
            if self._state == "rest" and val > peak_th:
                self._state = "peak"
            elif self._state == "peak" and val < rest_th:
                now = time.time()
                if now - self._last_rep_time >= min_sec:
                    rep_completed = True
                    self._last_rep_time = now
                self._state = "rest"

        return rep_completed

    def count_rep(self, landmarks, exercise_name):
        """Alias for process()."""
        return self.process(landmarks, exercise_name)

    def reset(self):
        """Reset for a new exercise / new set."""
        self._smoothed_value = None
        self._state = "rest"
        self._last_rep_time = 0
        self._current_exercise = ""
        self.rep_count = 0

    def get_state(self):
        return {
            "rep_count": self.rep_count,
            "state": self._state,
            "smoothed_value": self._smoothed_value,
            "exercise": self._current_exercise,
            "status": "peak" if self._state == "peak" else "ready",
        }

    # -- internals --

    @staticmethod
    def _resolve_exercise(name):
        """Map various exercise name formats to a profile key."""
        n = name.lower().strip().replace("-", "_").replace(" ", "_")
        if n in EXERCISE_PROFILES:
            return n
        if n in EXERCISE_NAME_MAP:
            return EXERCISE_NAME_MAP[n]
        for keyword, key in EXERCISE_NAME_MAP.items():
            if keyword in n or n in keyword:
                return key
        return None

    @staticmethod
    def _compute_metric(lm, profile):
        """Compute the primary metric (angle or ratio) for this exercise."""
        joints = profile["joints"]
        use_min = profile.get("use_min", False)
        if joints == "rotation":
            return _shoulder_hip_ratio(lm)
        angles = []
        for side, i1, i2, i3 in joints:
            try:
                a = _angle_3pt(lm[i1], lm[i2], lm[i3])
                if a > 0:
                    angles.append(a)
            except Exception:
                continue
        if not angles:
            return None
        return float(min(angles)) if use_min else float(np.mean(angles))


# Factory function
def create_rep_counter():
    return RepCounterMediaPipe()
