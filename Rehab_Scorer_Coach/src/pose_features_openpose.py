from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class PoseFrameFeatures:
    vec_100: np.ndarray  # (100,)
    keypoints_25x4: np.ndarray  # (25,4)


class OpenPoseFeatureExtractor:
    """
    Converts normalized OpenPose keypoints (25,4) into Kimore-style 100-dim vector:
    [x1,y1,z1,score1, x2,y2,z2,score2, ...] => (100,)
    """
    def __init__(self, feature_dim: int = 100):
        if feature_dim != 100:
            raise ValueError("This extractor is designed for feature_dim=100 (25*4).")
        self.feature_dim = feature_dim

    def to_feature_vector(self, keypoints_25x4: np.ndarray) -> PoseFrameFeatures:
        if keypoints_25x4.shape != (25, 4):
            raise ValueError(f"Expected (25,4), got {keypoints_25x4.shape}")

        vec = keypoints_25x4.reshape(-1).astype(np.float32)  # (100,)
        return PoseFrameFeatures(vec_100=vec, keypoints_25x4=keypoints_25x4.astype(np.float32))


class PoseWindowBuffer:
    """
    Maintains rolling list of last T frames of 100-dim vectors.
    Produces window (1, T, 100). If not enough frames, pads by repeating last (or zeros).
    """
    def __init__(self, T: int = 100, F: int = 100):
        self.T = int(T)
        self.F = int(F)
        self._buf: List[np.ndarray] = []

    def reset(self) -> None:
        self._buf = []

    def push(self, vec: np.ndarray) -> None:
        vec = np.asarray(vec, dtype=np.float32)
        if vec.shape != (self.F,):
            raise ValueError(f"Expected vec shape ({self.F},), got {vec.shape}")
        self._buf.append(vec)
        if len(self._buf) > self.T:
            self._buf = self._buf[-self.T :]

    def window(self) -> Tuple[np.ndarray, str]:
        """
        Returns:
            X: (1,T,F)
            note: string about padding status (debug)
        """
        n = len(self._buf)
        if n == 0:
            X = np.zeros((1, self.T, self.F), dtype=np.float32)
            return X, "empty->zeros"

        if n < self.T:
            last = self._buf[-1]
            pad = [last.copy() for _ in range(self.T - n)]
            seq = self._buf + pad
            X = np.stack(seq, axis=0).astype(np.float32)[None, ...]
            return X, f"padded_{n}_to_{self.T}"

        X = np.stack(self._buf[-self.T :], axis=0).astype(np.float32)[None, ...]
        return X, "full"