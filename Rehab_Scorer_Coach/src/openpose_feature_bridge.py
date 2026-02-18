# Rehab_Scorer_Coach/src/openpose_feature_bridge.py
from __future__ import annotations

import numpy as np


class OpenPoseFeatureBridge:
    """
    Converts OpenPose BODY_25 (25 joints x [x,y,conf]) to 100-dim vector:
      per joint: [x_norm, y_norm, z=0, conf]
    Normalization:
      - root-center by MidHip (idx=8)
      - scale by shoulder width (2,5) else hip width (9,12) else 1.0
    """

    BODY25 = 25
    ROOT = 8  # MidHip
    RSHO = 2
    LSHO = 5
    RHIP = 9
    LHIP = 12

    def __init__(self, conf_floor: float = 0.05):
        self.conf_floor = float(conf_floor)

    def _safe_scale(self, xy: np.ndarray, conf: np.ndarray) -> float:
        def dist(i, j):
            if conf[i] > self.conf_floor and conf[j] > self.conf_floor:
                return float(np.linalg.norm(xy[i] - xy[j]))
            return None

        s = dist(self.RSHO, self.LSHO)
        if s is None:
            s = dist(self.RHIP, self.LHIP)
        if s is None or s < 1e-6:
            s = 1.0
        return float(s)

    def to_feat100(self, pose25x3: np.ndarray) -> np.ndarray:
        """
        pose25x3: shape (25,3) with columns [x,y,conf]
        returns: shape (100,) float32
        """
        if pose25x3.shape != (25, 3):
            raise ValueError(f"Expected (25,3), got {pose25x3.shape}")

        xy = pose25x3[:, :2].astype(np.float32)   # (25,2)
        conf = pose25x3[:, 2].astype(np.float32)  # (25,)

        # if root not confident, still proceed but less stable
        root_xy = xy[self.ROOT].copy()
        xy = xy - root_xy[None, :]

        scale = self._safe_scale(xy, conf)
        xy = xy / scale

        z = np.zeros((25, 1), dtype=np.float32)
        c = conf.reshape(25, 1).astype(np.float32)

        feat = np.concatenate([xy, z, c], axis=1).reshape(-1)  # 25*4 = 100
        return feat.astype(np.float32)