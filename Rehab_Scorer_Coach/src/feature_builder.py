import numpy as np

# 25 landmark indices -> 25*(x,y,z,vis)=100 features
IDX25 = [
    0,        # nose
    11, 12,   # shoulders
    13, 14,   # elbows
    15, 16,   # wrists
    23, 24,   # hips
    25, 26,   # knees
    27, 28,   # ankles
    31, 32,   # foot index
    7, 8,     # ears
    19, 20,   # index finger
    21, 22,   # thumbs
    1, 2, 3, 4 # eyes
]

def landmarks_to_feature100(landmarks) -> np.ndarray:
    """
    landmarks: list of 33 MediaPipe landmarks.
    returns: (100,) float32
    """
    feat = []
    for i in IDX25:
        p = landmarks[i]
        vis = getattr(p, "visibility", None)
        if vis is None:
            vis = getattr(p, "presence", 1.0)
        feat.extend([p.x, p.y, p.z, float(vis)])
    return np.array(feat, dtype=np.float32)

def resample_to_T(seq: np.ndarray, T: int) -> np.ndarray:
    """
    seq: (n, F) -> (T, F) by index interpolation.
    """
    n = seq.shape[0]
    if n == 0:
        return np.zeros((T, seq.shape[1]), dtype=np.float32)
    if n == T:
        return seq.astype(np.float32)
    idx = np.linspace(0, n - 1, T).astype(np.int32)
    return seq[idx].astype(np.float32)