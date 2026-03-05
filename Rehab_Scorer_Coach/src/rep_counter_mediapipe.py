"""
MediaPipe Angle-Based Rep Counter for Rehabilitation Exercises

Standard approach used across AI fitness / pose estimation projects
(Google MediaPipe docs, Nicholas Renotte, LearnOpenCV AI Fitness Trainer):

  1. Calculate joint angle from 3 MediaPipe landmarks
  2. Light EMA smoothing (alpha=0.6 — mostly raw, handles jitter)
  3. Two-threshold hysteresis state machine (rest <-> peak)
  4. Count rep on peak -> rest transition
  5. Minimum time between reps to prevent doubles

NO quality gates, NO form checks — the angle transition is the
only criterion for rep counting. This is the widely-accepted method.

Supports:  Kimore  -> squat, lifting_of_arms, lateral_trunk_tilt, trunk_rotation
           Keraal  -> forward_flexion, flank_stretch, torso_rotation
"""

import numpy as np
import time
from typing import Dict, Optional


# --- MediaPipe BlazePose 33 landmark indices ---
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28
NOSE = 0


# --- Standard calculate_angle (atan2 method) ---
# Identical to the function used in every MediaPipe fitness tutorial.
# Returns angle at the VERTEX point b, in degrees [0, 180].

def calculate_angle(a, b, c):
    """
    Calculate angle at vertex b formed by points a -> b -> c.
    Uses the atan2 method (standard in MediaPipe tutorials).
    a, b, c: array-like with at least [x, y].
    Returns: angle in degrees [0, 180].
    """
    a = np.array(a[:2], dtype=float)
    b = np.array(b[:2], dtype=float)
    c = np.array(c[:2], dtype=float)

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - \
              np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return float(angle)


def _shoulder_hip_ratio(landmarks):
    """
    Ratio of shoulder width to hip width in the frontal plane.
    Drops from ~1.0 to ~0.5 when the torso rotates.
    """
    sw = abs(float(landmarks[L_SHOULDER][0]) - float(landmarks[R_SHOULDER][0]))
    hw = abs(float(landmarks[L_HIP][0]) - float(landmarks[R_HIP][0]))
    if hw < 1e-6:
        return 1.0
    return float(sw / hw)


def _forward_bend_ratio(landmarks):
    """
    Ratio that tracks forward flexion from a FRONT-facing camera.

    Standard shoulder-hip-knee angle only works from a side view.
    From the front camera, forward flexion compresses the vertical
    distance between nose and hips (head comes down toward waist).

    metric = |nose_y - hip_center_y| / |hip_center_y - knee_center_y|

    Standing:  nose is far above hips  → ratio ~1.5-2.0
    Bent fwd:  nose drops toward hips  → ratio ~0.5-1.0

    Direction: "down" (ratio DECREASES as person bends forward).
    """
    nose_y = float(landmarks[NOSE][1])
    hip_center_y = (float(landmarks[L_HIP][1]) + float(landmarks[R_HIP][1])) / 2.0
    knee_center_y = (float(landmarks[L_KNEE][1]) + float(landmarks[R_KNEE][1])) / 2.0

    # Denominator: hip-to-knee distance (normalises for person size / distance)
    denom = abs(knee_center_y - hip_center_y)
    if denom < 1e-6:
        return 1.5  # fallback

    return abs(hip_center_y - nose_y) / denom


# =====================================================================
# EXERCISE PROFILES
#
# Standard joint angles for rehabilitation exercises.
# Joint triplets: (side_label, point_A, vertex_B, point_C)
#   -> angle is measured AT vertex_B
#
# direction = "down" -> angle DECREASES to reach peak (squat, flexion)
# direction = "up"   -> angle INCREASES to reach peak (arm raise)
#
# Thresholds are set for REHAB patients (limited ROM), not athletes.
# =====================================================================

EXERCISE_PROFILES = {

    # -- KiMoRe exercises --

    # SQUAT: Knee angle (hip -> knee -> ankle)
    # Standing ~ 170 deg, rehab squat bottom ~ 90-130 deg
    # Wide gap so even gentle squats register
    "squat": {
        "joints": [
            ("L", L_HIP, L_KNEE, L_ANKLE),
            ("R", R_HIP, R_KNEE, R_ANKLE),
        ],
        "rest_threshold": 158,   # stand back up to ~158
        "peak_threshold": 140,   # bend knees to ≤140
        "direction": "down",
        "min_rep_sec": 0.3,
    },

    # LIFTING OF ARMS: Shoulder angle (hip -> shoulder -> wrist)
    # Arms down ~ 45-52 deg (sitting/standing), raised ~ 60-90+ deg
    # Gap = 6°: arms back to ~52 = rest, raise to ~58 = peak
    "lifting_of_arms": {
        "joints": [
            ("L", L_HIP, L_SHOULDER, L_WRIST),
            ("R", R_HIP, R_SHOULDER, R_WRIST),
        ],
        "rest_threshold": 52,    # arms back at sides (~49-52 natural)
        "peak_threshold": 58,    # meaningful arm raise
        "direction": "up",
        "min_rep_sec": 0.3,
    },

    # LATERAL TRUNK TILT: Trunk angle (shoulder -> hip -> knee)
    # Standing ~ 170 deg, tilted ~ 145-155 deg. Use MIN of L/R.
    # Gap = 6°: easy cycle for side tilts
    "lateral_trunk_tilt": {
        "joints": [
            ("L", L_SHOULDER, L_HIP, L_KNEE),
            ("R", R_SHOULDER, R_HIP, R_KNEE),
        ],
        "rest_threshold": 164,
        "peak_threshold": 158,
        "direction": "down",
        "min_rep_sec": 0.3,
        "use_min": True,
    },

    # TRUNK ROTATION: shoulder-width / hip-width ratio
    # Facing camera ~ 0.9-1.0, rotated ~ 0.3-0.6
    # Wide gap for reliable cycling
    "trunk_rotation": {
        "joints": "rotation",
        "rest_threshold": 0.88,
        "peak_threshold": 0.68,
        "direction": "down",
        "min_rep_sec": 0.3,
    },

    # -- Keraal exercises (low back pain) --

    # FORWARD FLEXION: nose-to-hip vertical distance ratio
    # Uses special "forward_bend" metric that works from front camera.
    # Standing: ratio ~1.5-2.0  |  Bent forward: ratio ~0.7-1.2
    # Rehab patients do gentle bends, so thresholds are close.
    "forward_flexion": {
        "joints": "forward_bend",
        "rest_threshold": 1.45,   # standing back up: nose far above hips
        "peak_threshold": 1.25,   # gentle bend: nose closer to hips
        "direction": "down",
        "min_rep_sec": 0.5,
    },

    # FLANK STRETCH: Trunk angle (shoulder -> hip -> knee), MIN of L/R
    # Gap = 6°: easy cycle for side stretches
    "flank_stretch": {
        "joints": [
            ("L", L_SHOULDER, L_HIP, L_KNEE),
            ("R", R_SHOULDER, R_HIP, R_KNEE),
        ],
        "rest_threshold": 164,
        "peak_threshold": 158,
        "direction": "down",
        "min_rep_sec": 0.5,
        "use_min": True,
    },

    # TORSO ROTATION: shoulder/hip width ratio
    # Facing camera: shoulders wider than hips, ratio ~1.2-1.6
    # Rotated: shoulders compress, ratio drops to ~0.8-1.1
    "torso_rotation": {
        "joints": "rotation",
        "rest_threshold": 1.15,
        "peak_threshold": 1.0,
        "direction": "down",
        "min_rep_sec": 0.5,
    },

    # TRUNK ROTATION TARGET (Kimore variant)
    # Wide gap for reliable cycling
    "trunk_rotation_target": {
        "joints": "rotation",
        "rest_threshold": 0.85,
        "peak_threshold": 0.65,
        "direction": "down",
        "min_rep_sec": 0.5,
    },

    # PELVIS ROTATION
    # Wide gap for reliable cycling
    "pelvis_rotation": {
        "joints": "rotation",
        "rest_threshold": 0.85,
        "peak_threshold": 0.65,
        "direction": "down",
        "min_rep_sec": 0.5,
    },
}


# -- Name resolution map --
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
    # Keraal exercise codes
    "ctk": "forward_flexion",
    "elk": "flank_stretch",
    "rtk": "torso_rotation",
}


# =====================================================================
# RepCounterMediaPipe  --  THE STANDARD APPROACH
# =====================================================================

class RepCounterMediaPipe:
    """
    Standard MediaPipe angle-based rep counter.

    This is the same algorithm used in:
      - Nicholas Renotte's "AI Pose Estimation" tutorial
      - LearnOpenCV "AI Fitness Trainer with MediaPipe"
      - Google's MediaPipe Pose classification sample

    Algorithm:
      1. Compute angle at the relevant joint
      2. Light EMA smoothing (alpha=0.6)
      3. Two-threshold state machine:
           rest  -> peak   when value crosses peak_threshold
           peak  -> rest   when value crosses rest_threshold  ->  COUNT REP
      4. Minimum time between reps (prevents doubles)

    Usage:
        counter = RepCounterMediaPipe()
        for each frame:
            rep_done = counter.process(landmarks_33x3, "squat")
            if rep_done:
                total_reps += 1
    """

    # EMA alpha = 0.85: near-instant tracking, minimal lag.
    # At any FPS the smoothed value catches up within 1 frame.
    EMA_ALPHA = 0.85

    def __init__(self):
        self._smoothed_value = None
        self._state = "rest"          # "rest" or "peak"
        self._last_rep_time = 0.0
        self._current_exercise = ""
        self.rep_count = 0            # backward compat
        self._dbg_ctr = 0

    # -- public API --

    def process(self, landmarks, exercise_name: str) -> bool:
        """
        Feed one frame. Returns True when a rep is completed.

        landmarks: ndarray (33, 3) or (33, 4) -- MediaPipe pose.
                   Values can be in [0,1] (normalized) or pixel coords.
        exercise_name: string matching an EXERCISE_PROFILES key or alias.
        """
        if landmarks is None or len(landmarks) < 33:
            return False

        lm = np.array(landmarks, dtype=float)

        # Normalise pixel coords -> [0, 1] if they look like pixels
        if lm[:, :2].max() > 2.0:
            lm[:, 0] /= max(lm[:, 0].max(), 1.0)
            lm[:, 1] /= max(lm[:, 1].max(), 1.0)

        # Resolve exercise name
        key = self._resolve_exercise(exercise_name)
        if key is None:
            return False

        # Reset if exercise changed
        if key != self._current_exercise:
            self._smoothed_value = None
            self._state = "rest"
            self._current_exercise = key

        profile = EXERCISE_PROFILES[key]

        # -- 1. Compute raw angle / ratio --
        raw = self._compute_metric(lm, profile)
        if raw is None:
            return False

        # -- 2. Light EMA smoothing --
        if self._smoothed_value is None:
            self._smoothed_value = raw
        else:
            self._smoothed_value = (
                self.EMA_ALPHA * raw +
                (1.0 - self.EMA_ALPHA) * self._smoothed_value
            )
        val = self._smoothed_value

        # -- 3. Two-threshold state machine --
        direction = profile["direction"]
        rest_th  = profile["rest_threshold"]
        peak_th  = profile["peak_threshold"]
        min_sec  = profile.get("min_rep_sec", 1.0)

        rep_completed = False

        if direction == "down":
            # angle DECREASES toward peak (e.g., squat)
            if self._state == "rest" and val < peak_th:
                self._state = "peak"
                print(f"      [REP {key}] rest->peak (val={val:.1f} < {peak_th})")
            elif self._state == "peak" and val > rest_th:
                elapsed = time.time() - self._last_rep_time
                if elapsed >= min_sec:
                    rep_completed = True
                    self._last_rep_time = time.time()
                    print(f"      [REP {key}] *** REP COMPLETE *** (val={val:.1f} > {rest_th}, {elapsed:.1f}s)")
                else:
                    print(f"      [REP {key}] peak->rest too fast ({elapsed:.1f}s < {min_sec}s)")
                self._state = "rest"
        else:
            # angle INCREASES toward peak (e.g., arm raise)
            if self._state == "rest" and val > peak_th:
                self._state = "peak"
                print(f"      [REP {key}] rest->peak (val={val:.1f} > {peak_th})")
            elif self._state == "peak" and val < rest_th:
                elapsed = time.time() - self._last_rep_time
                if elapsed >= min_sec:
                    rep_completed = True
                    self._last_rep_time = time.time()
                    print(f"      [REP {key}] *** REP COMPLETE *** (val={val:.1f} < {rest_th}, {elapsed:.1f}s)")
                else:
                    print(f"      [REP {key}] peak->rest too fast ({elapsed:.1f}s < {min_sec}s)")
                self._state = "rest"

        # Log EVERY frame for debugging (critical for tuning thresholds)
        self._dbg_ctr += 1
        print(f"      [REP {key}] raw={raw:.2f} smooth={val:.2f} state={self._state} "
              f"(rest{'>' if direction=='down' else '<'}{rest_th:.2f} "
              f"peak{'<' if direction=='down' else '>'}{peak_th:.2f})")

        return rep_completed

    def count_rep(self, landmarks, exercise_name: str) -> bool:
        """Alias for process()."""
        return self.process(landmarks, exercise_name)

    def reset(self):
        """Reset for new exercise / new set."""
        self._smoothed_value = None
        self._state = "rest"
        self._last_rep_time = 0.0
        self._current_exercise = ""
        self.rep_count = 0
        self._dbg_ctr = 0

    def get_state(self) -> dict:
        return {
            "rep_count": self.rep_count,
            "state": self._state,
            "smoothed_value": self._smoothed_value,
            "exercise": self._current_exercise,
            "status": "peak" if self._state == "peak" else "ready",
        }

    # -- internals --

    @staticmethod
    def _resolve_exercise(name: str) -> Optional[str]:
        """Map exercise display name / alias to a profile key."""
        n = name.lower().strip().replace("-", "_").replace(" ", "_")
        if n in EXERCISE_PROFILES:
            return n
        if n in EXERCISE_NAME_MAP:
            return EXERCISE_NAME_MAP[n]
        # Fuzzy fallback
        for keyword, key in EXERCISE_NAME_MAP.items():
            if keyword in n or n in keyword:
                return key
        return None

    @staticmethod
    def _compute_metric(lm, profile) -> Optional[float]:
        """Compute angle or ratio for this exercise profile."""
        joints = profile["joints"]
        use_min = profile.get("use_min", False)

        if joints == "rotation":
            return _shoulder_hip_ratio(lm)

        if joints == "forward_bend":
            return _forward_bend_ratio(lm)

        angles = []
        for side, i1, i2, i3 in joints:
            try:
                a = calculate_angle(lm[i1], lm[i2], lm[i3])
                if a > 0:
                    angles.append(a)
            except Exception:
                continue

        if not angles:
            return None

        return float(min(angles)) if use_min else float(np.mean(angles))


# -- Factory --
def create_rep_counter():
    return RepCounterMediaPipe()
