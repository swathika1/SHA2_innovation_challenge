import numpy as np


# ============================================================
# 1️⃣ Convert OpenPose 25 keypoints → 100D Kimore-style feature
# ============================================================

def openpose25_to_feature100(lm25: np.ndarray) -> np.ndarray:
    """
    lm25: (25,4) array from OpenPose [x,y,confidence,?]

    Output:
        feature100: (100,) flattened normalized pose
    """

    if lm25 is None:
        raise ValueError("lm25 is None")

    lm25 = np.asarray(lm25, dtype=np.float32)

    if lm25.shape[0] != 25:
        raise ValueError(f"Expected 25 keypoints, got {lm25.shape}")

    # Take x,y only (ignore confidence)
    xy = lm25[:, :2]  # (25,2)

    # -------- Normalize coordinates ----------
    # Use mid-hip as origin (OpenPose index 8)
    root = xy[8]

    xy_centered = xy - root

    # Scale by torso length (neck to mid-hip)
    neck = xy[1]
    torso_len = np.linalg.norm(neck - root)

    if torso_len < 1e-6:
        torso_len = 1.0

    xy_norm = xy_centered / torso_len

    # Flatten
    flat = xy_norm.flatten()  # (50,)

    # Duplicate to reach 100D (Kimore expects 100 features)
    # You trained on 100 dims. We replicate structure.
    feat100 = np.concatenate([flat, flat], axis=0)  # (100,)

    return feat100.astype(np.float32)


# ============================================================
# 2️⃣ Temporal Resampling (CRITICAL for Transformer model)
# ============================================================

def resample_to_T(seq: np.ndarray, T: int) -> np.ndarray:
    """
    seq: (N, F)
    Returns: (T, F)

    Linear interpolation across time dimension.
    """

    seq = np.asarray(seq, dtype=np.float32)

    if seq.ndim != 2:
        raise ValueError(f"Expected (N,F), got {seq.shape}")

    N, F = seq.shape

    if N == T:
        return seq

    if N < 2:
        # repeat single frame
        return np.repeat(seq, T, axis=0)

    # Original time indices
    old_idx = np.linspace(0, 1, N)
    new_idx = np.linspace(0, 1, T)

    out = np.zeros((T, F), dtype=np.float32)

    for f in range(F):
        out[:, f] = np.interp(new_idx, old_idx, seq[:, f])

    return out