from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.openpose_client import OpenPoseHTTPClient
from Rehab_Scorer_Coach.src.pose_features_openpose import OpenPoseFeatureExtractor, PoseWindowBuffer
from Rehab_Scorer_Coach.src.exercise_model_infer import ExerciseModelInfer


@dataclass
class OpenPoseSharedState:
    last_vec_100: Optional[np.ndarray] = None
    last_window: Optional[np.ndarray] = None
    last_note: str = ""


class OpenPoseUnifiedPipeline:
    """
    Produces ONE window tensor (1,100,100) from OpenPose.
    That SAME window is fed to exercise + score models.
    """

    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or AppConfig()
        self.client = OpenPoseHTTPClient(self.cfg.openpose_url)
        self.fe = OpenPoseFeatureExtractor(feature_dim=self.cfg.feature_dim)
        self.buf = PoseWindowBuffer(T=self.cfg.target_timesteps, F=self.cfg.feature_dim)

        # attach models here (exercise shown; score you attach similarly)
        self.exercise_model = ExerciseModelInfer(self.cfg)

        self.state = OpenPoseSharedState()

    def reset(self) -> None:
        self.buf.reset()
        self.state = OpenPoseSharedState()

    def ingest_frame(self, bgr: np.ndarray) -> Dict[str, Any]:
        """
        Returns dict containing:
            - X_window (1,100,100)
            - exercise prediction + full probs vector
        """
        op = self.client.infer_keypoints(bgr)
        feats = self.fe.to_feature_vector(op.keypoints_25x4)

        self.buf.push(feats.vec_100)
        X, note = self.buf.window()

        self.state.last_vec_100 = feats.vec_100
        self.state.last_window = X
        self.state.last_note = note

        # EXERCISE
        ex_pred = self.exercise_model.predict_window(X, top_k=5)

        out = {
            "pose_vec_100": feats.vec_100.tolist(),
            "window_note": note,
            "exercise_label": ex_pred.label,
            "exercise_best_id": ex_pred.best_id,
            "exercise_confidence": ex_pred.confidence,
            "exercise_probs_vector": ex_pred.probs_vector,   # FULL VECTOR ALWAYS
            "exercise_topk": ex_pred.topk,
        }
        print(f"[EX_MODEL] {note} raw={ex_pred.label} id={ex_pred.best_id} p={ex_pred.confidence:.4f}")
        return out