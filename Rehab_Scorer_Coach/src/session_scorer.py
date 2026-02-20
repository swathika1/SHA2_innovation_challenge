from collections import deque
import numpy as np

class SessionScorer:
    """
    Tracks clip scores and provides:
      - rolling smoothed score
      - overall session score
      - JSON output
    """
    def __init__(self, smoothing_window: int = 5):
        self.clip_scores = []
        self.recent_scores = deque(maxlen=max(1, smoothing_window))

    def add_clip_score(self, score: float):
        s = float(score)
        self.clip_scores.append(s)
        self.recent_scores.append(s)

    def smoothed_score(self) -> float:
        if not self.recent_scores:
            return 0.0
        return float(np.mean(self.recent_scores))

    def overall_score(self) -> float:
        if not self.clip_scores:
            return 0.0
        return float(np.mean(self.clip_scores))

    def to_json(self):
        return {"Overall Session Score": round(self.overall_score(), 2)}
