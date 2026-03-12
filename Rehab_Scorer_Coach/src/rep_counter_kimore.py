"""
Kimore Rep Counter — Motion-Based (Hysteresis State Machine)

Counts reps for all 5 Kimore rehabilitation exercises using actual
pose signal analysis instead of time-based heuristics.

Exercises supported:
  - arm_lifting / lifting_of_arms
  - lateral_trunk_tilt (with crouch anti-hack)
  - trunk_rotation (with baseline calibration)
  - pelvis_rotation (with baseline calibration)
  - squat

Algorithm per exercise:
  1. Compute a raw signal from MediaPipe 33-point landmarks
  2. Apply EMA smoothing
  3. Two-threshold hysteresis state machine (WAIT_HIGH / WAIT_LOW)
  4. Optional baseline calibration (rotation exercises)
  5. Optional crouch anti-hack (lateral tilt)
  6. Minimum ROM range + minimum time between reps to prevent doubles

Compatible with web_pipeline.py interface:
    rep_counter.reset(exercise_name)
    rep_counter.update(exercise_name, angles_dict)       # angles_dict based
    rep_counter.update_landmarks(exercise_name, landmarks)  # raw landmarks based
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

import numpy as np


# ── MediaPipe BlazePose 33 landmark indices ──
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW,    R_ELBOW    = 13, 14
L_WRIST,    R_WRIST    = 15, 16
L_HIP,      R_HIP      = 23, 24
L_KNEE,     R_KNEE     = 25, 26
L_ANKLE,    R_ANKLE    = 27, 28
NOSE = 0


@dataclass
class RepInfo:
    reps: int
    phase: str
    note: str


# ══════════════════════════════════════════════════════════════════════
#  ANGLE / SIGNAL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _angle_3pts(a, b, c):
    """Angle at vertex b (degrees) from points a-b-c, using [x, y]."""
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])

    abx, aby = ax - bx, ay - by
    cbx, cby = cx - bx, cy - by

    dot = abx * cbx + aby * cby
    ab = math.hypot(abx, aby)
    cb = math.hypot(cbx, cby)
    if ab * cb < 1e-9:
        return None
    cosv = max(-1.0, min(1.0, dot / (ab * cb)))
    return math.degrees(math.acos(cosv))


def _vis_ok(lm, idx, min_vis=0.5):
    """Check landmark visibility (z channel used as confidence in mp.solutions.pose)."""
    if len(lm[idx]) >= 4:
        return float(lm[idx][3]) >= min_vis
    # When using mp.solutions.pose, z is depth not visibility — assume visible
    return True


def _yaw_xz_deg(p1, p2):
    """Yaw angle from p1 to p2 in the x-z plane (degrees)."""
    dx = float(p2[0]) - float(p1[0])
    dz = float(p2[2]) - float(p1[2]) if len(p2) > 2 and len(p1) > 2 else 0.0
    return math.degrees(math.atan2(dz, dx))


def _wrap180(d):
    return (d + 180) % 360 - 180


def _yaw_mod_180(deg):
    """Make yaw 180°-invariant by mapping to [-90, +90]."""
    d = _wrap180(deg)
    if d > 90:
        d -= 180
    elif d < -90:
        d += 180
    return d


# ══════════════════════════════════════════════════════════════════════
#  SIGNAL FUNCTIONS  (one per exercise)
# ══════════════════════════════════════════════════════════════════════

def signal_arm_lifting(lm):
    """
    Arm lifting signal: how far above the shoulders are the wrists,
    normalised by torso length.  Returns a ratio (0 = at shoulder, >0 = above).
    """
    shoulder_y = (float(lm[L_SHOULDER][1]) + float(lm[R_SHOULDER][1])) / 2.0
    hip_y = (float(lm[L_HIP][1]) + float(lm[R_HIP][1])) / 2.0
    torso = abs(hip_y - shoulder_y)
    if torso < 1e-6:
        return None
    left = (shoulder_y - float(lm[L_WRIST][1])) / torso
    right = (shoulder_y - float(lm[R_WRIST][1])) / torso
    return min(left, right)


def signal_trunk_tilt(lm):
    """
    Lateral trunk tilt: deviation from vertical (mid-hip -> mid-shoulder).
    Upright ≈ 0°, side bend increases.
    """
    sx = (float(lm[L_SHOULDER][0]) + float(lm[R_SHOULDER][0])) / 2.0
    sy = (float(lm[L_SHOULDER][1]) + float(lm[R_SHOULDER][1])) / 2.0
    hx = (float(lm[L_HIP][0]) + float(lm[R_HIP][0])) / 2.0
    hy = (float(lm[L_HIP][1]) + float(lm[R_HIP][1])) / 2.0

    dx = sx - hx
    dy = sy - hy
    return abs(math.degrees(math.atan2(dx, -dy)))


def signal_trunk_rotation(lm):
    """
    Trunk rotation: signed rotation proxy (shoulder line vs hip line, 180°-invariant).
    Needs baseline subtraction — raw signed value returned.
    """
    yaw_sh = _yaw_xz_deg(lm[L_SHOULDER], lm[R_SHOULDER])
    yaw_hp = _yaw_xz_deg(lm[L_HIP], lm[R_HIP])
    rel = _wrap180(yaw_sh - yaw_hp)
    return _yaw_mod_180(rel)


def signal_pelvis_rotation(lm):
    """
    Pelvis rotation: hip line yaw (180°-invariant).
    Needs baseline subtraction — raw signed value returned.
    """
    yaw_deg = _yaw_xz_deg(lm[L_HIP], lm[R_HIP])
    return _yaw_mod_180(yaw_deg)


def signal_squat(lm):
    """
    Squat: min knee angle (hip -> knee -> ankle).
    Standing ≈ 165-180°, deep squat < 100°.
    """
    angles = []
    # Left knee
    la = _angle_3pts(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE])
    if la is not None:
        angles.append(la)
    # Right knee
    ra = _angle_3pts(lm[R_HIP], lm[R_KNEE], lm[R_ANKLE])
    if ra is not None:
        angles.append(ra)
    return min(angles) if angles else None


def _height_proxy(lm):
    """Average hip y — used as crouch detection proxy."""
    return (float(lm[L_HIP][1]) + float(lm[R_HIP][1])) / 2.0


# ══════════════════════════════════════════════════════════════════════
#  EXERCISE SPECS
# ══════════════════════════════════════════════════════════════════════

@dataclass
class _ExSpec:
    """Internal exercise specification."""
    signal_fn: object                # callable(lm) -> float | None
    high_means_effort: bool          # True: HIGH->LOW counts;  False: LOW->HIGH (squat)
    up_threshold: float
    down_threshold: float
    ema_alpha: float = 0.25
    min_seconds: float = 0.4
    min_range: float = 0.0
    needs_baseline: bool = False     # trunk_rotation, pelvis_rotation
    needs_crouch_gate: bool = False  # lateral_trunk_tilt


_EXERCISE_SPECS: Dict[str, _ExSpec] = {
    "arm_lifting": _ExSpec(
        signal_fn=signal_arm_lifting,
        high_means_effort=True,
        up_threshold=0.35,
        down_threshold=0.15,
        min_range=0.12,
        min_seconds=0.35,
    ),
    "lifting_of_arms": _ExSpec(        # alias
        signal_fn=signal_arm_lifting,
        high_means_effort=True,
        up_threshold=0.35,
        down_threshold=0.15,
        min_range=0.12,
        min_seconds=0.35,
    ),
    "lateral_trunk_tilt": _ExSpec(
        signal_fn=signal_trunk_tilt,
        high_means_effort=True,
        up_threshold=18,
        down_threshold=8,
        min_range=5,
        min_seconds=0.40,
        needs_crouch_gate=True,
    ),
    "trunk_rotation": _ExSpec(
        signal_fn=signal_trunk_rotation,
        high_means_effort=True,
        up_threshold=20,
        down_threshold=8,
        min_range=8,
        min_seconds=0.45,
        needs_baseline=True,
    ),
    "pelvis_rotation": _ExSpec(
        signal_fn=signal_pelvis_rotation,
        high_means_effort=True,
        up_threshold=12,
        down_threshold=5,
        min_range=4,
        min_seconds=0.45,
        needs_baseline=True,
    ),
    "squat": _ExSpec(
        signal_fn=signal_squat,
        high_means_effort=False,      # LOW -> HIGH counts
        up_threshold=165,
        down_threshold=95,
        min_range=20,
        min_seconds=0.50,
    ),
}

# ── Name resolution ──
_NAME_MAP: Dict[str, str] = {
    "arm_lifting": "arm_lifting",
    "lifting_of_arms": "lifting_of_arms",
    "lifting of arms": "lifting_of_arms",
    "lateral_trunk_tilt": "lateral_trunk_tilt",
    "lateral trunk tilt": "lateral_trunk_tilt",
    "lateral_trunk_tilt_with_arms_in_extension": "lateral_trunk_tilt",
    "trunk_rotation": "trunk_rotation",
    "trunk rotation": "trunk_rotation",
    "pelvis_rotation": "pelvis_rotation",
    "pelvis rotation": "pelvis_rotation",
    "squat": "squat",
}


def _resolve_name(name: str) -> Optional[str]:
    """Resolve display / alias name to a _EXERCISE_SPECS key."""
    n = name.lower().strip().replace("-", "_")
    if n in _EXERCISE_SPECS:
        return n
    n2 = n.replace("_", " ")
    if n2 in _NAME_MAP:
        return _NAME_MAP[n2]
    if n in _NAME_MAP:
        return _NAME_MAP[n]
    # Fuzzy substring
    for keyword, key in _NAME_MAP.items():
        if keyword in n or n in keyword:
            return key
    return None


# ══════════════════════════════════════════════════════════════════════
#  INTERNAL STATE MACHINE (one per exercise)
# ══════════════════════════════════════════════════════════════════════

class _ExState:
    """Per-exercise hysteresis state machine with EMA, range tracking, baseline."""

    def __init__(self, spec: _ExSpec):
        self.spec = spec
        self.reps = 0
        self.ema: Optional[float] = None
        self.vmin: Optional[float] = None
        self.vmax: Optional[float] = None
        self.last_time = 0.0
        self.state = "WAIT_HIGH" if spec.high_means_effort else "WAIT_LOW"

        # Baseline calibration (rotation exercises)
        self.baseline_start: Optional[float] = None
        self.baseline_value: Optional[float] = None
        self.baseline_ready = False
        self.BASELINE_SECONDS = 2.0

        # Crouch gate (lateral tilt)
        self.height_base_start: Optional[float] = None
        self.height_base: Optional[float] = None
        self.height_ready = False
        self.HEIGHT_BASELINE_SECONDS = 1.0
        self.CROUCH_BLOCK_RATIO = 0.90

    def _smooth(self, x: float) -> float:
        if self.ema is None:
            self.ema = x
        else:
            a = self.spec.ema_alpha
            self.ema = a * x + (1 - a) * self.ema
        return self.ema

    def _track_range(self, v: float):
        self.vmin = v if self.vmin is None else min(self.vmin, v)
        self.vmax = v if self.vmax is None else max(self.vmax, v)

    def _range_ok(self) -> bool:
        if self.spec.min_range <= 0:
            return True
        if self.vmin is None or self.vmax is None:
            return False
        return (self.vmax - self.vmin) >= self.spec.min_range

    def _reset_range(self):
        self.vmin = None
        self.vmax = None

    def calibrate_baseline(self, raw: float, now: float) -> tuple:
        """Returns (baseline_value, is_ready)."""
        if self.baseline_start is None:
            self.baseline_start = now
        if (now - self.baseline_start) <= self.BASELINE_SECONDS:
            if self.baseline_value is None:
                self.baseline_value = raw
            else:
                self.baseline_value = 0.1 * raw + 0.9 * self.baseline_value
            self.baseline_ready = False
        else:
            self.baseline_ready = True
        return self.baseline_value, self.baseline_ready

    def calibrate_height(self, h: float, now: float) -> tuple:
        """Returns (height_base, is_ready)."""
        if self.height_base_start is None:
            self.height_base_start = now
        if (now - self.height_base_start) <= self.HEIGHT_BASELINE_SECONDS:
            if self.height_base is None:
                self.height_base = h
            else:
                self.height_base = 0.1 * h + 0.9 * self.height_base
            self.height_ready = False
        else:
            self.height_ready = True
        return self.height_base, self.height_ready

    def update(self, val: Optional[float]) -> tuple:
        """
        Feed one signal value.
        Returns (reps, state_str, ema_value, rep_incremented_bool).
        """
        if val is None:
            return self.reps, self.state, self.ema, False

        now = time.time()
        s = self._smooth(val)
        self._track_range(s)

        can_count = (now - self.last_time) >= self.spec.min_seconds
        up = self.spec.up_threshold
        down = self.spec.down_threshold
        rep_incremented = False

        if self.spec.high_means_effort:
            # HIGH -> LOW counts
            if self.state == "WAIT_HIGH":
                if s >= up:
                    self.state = "WAIT_LOW"
            else:
                if s <= down and can_count and self._range_ok():
                    self.reps += 1
                    self.last_time = now
                    self.state = "WAIT_HIGH"
                    self._reset_range()
                    rep_incremented = True
        else:
            # LOW -> HIGH counts (squat)
            if self.state == "WAIT_LOW":
                if s <= down:
                    self.state = "WAIT_HIGH"
            else:
                if s >= up and can_count and self._range_ok():
                    self.reps += 1
                    self.last_time = now
                    self.state = "WAIT_LOW"
                    self._reset_range()
                    rep_incremented = True

        return self.reps, self.state, self.ema, rep_incremented


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC CLASS — KimoreRepCounter
# ══════════════════════════════════════════════════════════════════════

class KimoreRepCounter:
    """
    Motion-based rep counter for Kimore rehabilitation exercises.

    Supports two calling conventions:

    1) Landmark-based (preferred — pass raw 33×3 landmarks):
           rep_counter.update_landmarks(exercise_name, landmarks_33x3)

    2) Angle-dict based (backward compat with web_pipeline placeholder):
           rep_counter.update(exercise_name, angles_dict)
           ⤷ requires 'landmarks' key in angles_dict for full accuracy,
             otherwise falls back to angle-only heuristics.
    """

    def __init__(self):
        self.exercise_name: str = "unknown"
        self.reps: int = 0
        self.phase: str = "idle"
        self._states: Dict[str, _ExState] = {}

    def _get_state(self, ex_key: str) -> _ExState:
        if ex_key not in self._states:
            spec = _EXERCISE_SPECS[ex_key]
            self._states[ex_key] = _ExState(spec)
        return self._states[ex_key]

    def reset(self, exercise_name: str = "unknown"):
        self.exercise_name = exercise_name or "unknown"
        self.reps = 0
        self.phase = "idle"
        self._states = {}

    # ── Primary API: raw landmarks ──

    def update_landmarks(self, exercise_name: str, landmarks) -> RepInfo:
        """
        Count reps from raw MediaPipe 33×3 (or 33×4) landmarks.

        Parameters
        ----------
        exercise_name : str
        landmarks : np.ndarray (33, 3+) or list of 33 [x, y, z, ...]

        Returns
        -------
        RepInfo
        """
        if exercise_name and exercise_name != self.exercise_name:
            self.reset(exercise_name)
            self.exercise_name = exercise_name

        ex_key = _resolve_name(exercise_name)
        if ex_key is None:
            return RepInfo(reps=self.reps, phase="unknown_exercise",
                           note=f"Unrecognised exercise: {exercise_name}")

        lm = np.array(landmarks, dtype=float)
        if lm.shape[0] < 33:
            return RepInfo(reps=self.reps, phase=self.phase,
                           note="Not enough landmarks")

        spec = _EXERCISE_SPECS[ex_key]
        st = self._get_state(ex_key)
        now = time.time()

        # 1. Compute raw signal
        raw = spec.signal_fn(lm)
        if raw is None:
            reps, state, ema, _ = st.update(None)
            self.reps = reps
            self.phase = state
            return RepInfo(reps=reps, phase=state, note="signal=None (low visibility)")

        # 2. Baseline correction (rotation exercises)
        if spec.needs_baseline:
            base, ready = st.calibrate_baseline(raw, now)
            if base is None or not ready:
                self.phase = "calibrating"
                return RepInfo(reps=self.reps, phase="calibrating",
                               note=f"Baseline calibrating... raw={raw:.2f}")
            raw = abs(raw - base)

        # 3. Crouch anti-hack (lateral trunk tilt)
        crouch_block = False
        if spec.needs_crouch_gate:
            h = _height_proxy(lm)
            base_h, ready_h = st.calibrate_height(h, now)
            if h is not None and base_h is not None:
                crouch_block = (h > (2 - st.CROUCH_BLOCK_RATIO) * base_h)

        # 4. Update state machine
        if crouch_block:
            reps, state, ema, inc = st.update(None)
        else:
            reps, state, ema, inc = st.update(raw)

        self.reps = reps
        self.phase = state

        note_parts = [f"ex={ex_key}", f"raw={raw:.2f}"]
        if ema is not None:
            note_parts.append(f"ema={ema:.2f}")
        if crouch_block:
            note_parts.append("CROUCH_BLOCKED")
        if inc:
            note_parts.append("REP!")

        return RepInfo(reps=reps, phase=state, note=" | ".join(note_parts))

    # ── Backward-compatible API: angles_dict ──

    def update(self, exercise_name: str, angles_dict: Dict[str, float]) -> RepInfo:
        """
        Backward-compatible interface.

        If angles_dict contains a 'landmarks' key (np.ndarray 33×3),
        delegates to update_landmarks() for full accuracy.

        Otherwise falls back to angle-based heuristics for squat and arm lifting.
        """
        if exercise_name and exercise_name != self.exercise_name:
            self.reset(exercise_name)
            self.exercise_name = exercise_name

        # If raw landmarks are available, use the full pipeline
        if angles_dict and "landmarks" in angles_dict:
            lm = angles_dict["landmarks"]
            return self.update_landmarks(exercise_name, lm)

        # Fallback: angle-based heuristic for exercises where a single
        # joint angle is sufficient (squat, arm lifting)
        ex_key = _resolve_name(exercise_name)
        if ex_key is None:
            return RepInfo(reps=self.reps, phase="unknown_exercise",
                           note=f"Unrecognised exercise: {exercise_name}")

        st = self._get_state(ex_key)

        raw = self._extract_signal_from_angles(ex_key, angles_dict)
        reps, state, ema, inc = st.update(raw)
        self.reps = reps
        self.phase = state

        note = f"angle_fallback | ex={ex_key} | raw={raw}" + (" | REP!" if inc else "")
        return RepInfo(reps=reps, phase=state, note=note)

    @staticmethod
    def _extract_signal_from_angles(ex_key: str, angles: Dict[str, float]) -> Optional[float]:
        """
        Best-effort signal extraction from an angles dictionary.
        Keys expected: left_knee, right_knee, left_shoulder, right_shoulder, etc.
        """
        if not angles:
            return None

        if ex_key == "squat":
            vals = []
            for k in ("left_knee", "right_knee", "l_knee", "r_knee"):
                if k in angles and angles[k] is not None:
                    vals.append(float(angles[k]))
            return min(vals) if vals else None

        if ex_key in ("arm_lifting", "lifting_of_arms"):
            vals = []
            for k in ("left_shoulder", "right_shoulder", "l_shoulder", "r_shoulder"):
                if k in angles and angles[k] is not None:
                    vals.append(float(angles[k]))
            return max(vals) if vals else None

        if ex_key == "lateral_trunk_tilt":
            for k in ("trunk_tilt", "lateral_tilt", "torso_tilt"):
                if k in angles and angles[k] is not None:
                    return float(angles[k])
            return None

        # For rotation exercises without landmarks, we can't do much
        return None

    def get_state(self) -> Dict[str, Any]:
        return {
            "exercise": self.exercise_name,
            "reps": self.reps,
            "phase": self.phase,
        }