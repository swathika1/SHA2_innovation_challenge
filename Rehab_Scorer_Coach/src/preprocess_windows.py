# Rehab_Scorer_Coach/src/preprocess_windows.py
from __future__ import annotations
from collections import deque
from typing import Deque, Optional
import numpy as np

def stack_buffer(feat_buffer: Deque[np.ndarray]) -> Optional[np.ndarray]:
    # sourcery skip: inline-immediately-returned-variable
    """
    feat_buffer: deque of (F,) vectors
    returns: (N, F) float32
    """
    if feat_buffer is None or len(feat_buffer) == 0:
        return None
    feats = np.stack(list(feat_buffer), axis=0).astype(np.float32)  # (N,F)
    return feats

def resample_to_T(feats_NF: np.ndarray, T: int) -> np.ndarray:
    """
    Linear time resampling:
    feats_NF: (N, F)
    returns: (T, F)
    """
    N, F = feats_NF.shape
    if N == T:
        return feats_NF.astype(np.float32)

    # indices in original space
    x_old = np.linspace(0.0, 1.0, N, dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, T, dtype=np.float32)

    out = np.zeros((T, F), dtype=np.float32)
    for j in range(F):
        out[:, j] = np.interp(x_new, x_old, feats_NF[:, j]).astype(np.float32)
    return out

def build_window_1TF(
    feat_buffer: Deque[np.ndarray],
    T: int,
    use_last_only: bool = True,
) -> Optional[np.ndarray]:  # sourcery skip: assign-if-exp, hoist-statement-from-if, inline-immediately-returned-variable, merge-duplicate-blocks, remove-redundant-condition, remove-redundant-if
    """
    Returns (1, T, F) window ready for models.
    - If buffer has <2 frames: returns None
    - If buffer has N frames: takes last N (or full), resamples to T.
    """
    feats = stack_buffer(feat_buffer)
    if feats is None or feats.shape[0] < 2:
        return None
    if use_last_only:
        # take all available (deque already maxlen-limited)
        feats_NF = feats
    else:
        feats_NF = feats

    seq_TF = resample_to_T(feats_NF, T)           # (T,F)
    X_1TF = seq_TF[None, :, :].astype(np.float32) # (1,T,F)
    return X_1TF