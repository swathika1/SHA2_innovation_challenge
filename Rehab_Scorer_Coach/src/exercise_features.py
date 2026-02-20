# Rehab_Scorer_Coach/src/exercise_features.py
from __future__ import annotations
import numpy as np

L_HIP, R_HIP = 23, 24
L_SHO, R_SHO = 11, 12

def _pt(lm):
    # mediapipe NormalizedLandmark
    return np.array([float(lm.x), float(lm.y), float(getattr(lm, "z", 0.0))], dtype=np.float32)

def landmarks_to_posevec(landmarks, rotate_shoulders_horizontal: bool = True) -> np.ndarray:
    """
    Output: (F,) float32. MUST match training (order, normalization, everything).
    Example here: 33*(x,y,z)=99 with mid-hip centering + shoulder-width scaling + optional rotation.
    """
    pts = np.stack([_pt(lm) for lm in landmarks], axis=0)  # (33,3)

    mid_hip = (pts[L_HIP] + pts[R_HIP]) / 2.0
    pts = pts - mid_hip  # translate

    shoulder_width = np.linalg.norm(pts[L_SHO] - pts[R_SHO]) + 1e-6
    pts = pts / shoulder_width  # scale

    if rotate_shoulders_horizontal:
        # rotate in xy plane so shoulder line aligns with x-axis
        v = pts[R_SHO, :2] - pts[L_SHO, :2]
        ang = np.arctan2(v[1], v[0])
        c, s = np.cos(-ang), np.sin(-ang)
        R = np.array([[c, -s], [s, c]], dtype=np.float32)
        pts[:, :2] = pts[:, :2] @ R.T

    return pts.reshape(-1).astype(np.float32)  # (99,)
