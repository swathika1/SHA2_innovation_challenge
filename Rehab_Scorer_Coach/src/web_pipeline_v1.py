import contextlib
import time
from collections import deque
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.feature_builder_openpose import resample_to_T
from Rehab_Scorer_Coach.src.model_infer import ScoreModel
from Rehab_Scorer_Coach.src.rag_store import RAGStore
from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
from Rehab_Scorer_Coach.src.rep_counter_kimore import KimoreRepCounter
from Rehab_Scorer_Coach.src.exercise_model_infer import ExerciseModelInfer
from Rehab_Scorer_Coach.src.openpose_client import OpenPoseClient


class WebRehabPipeline:

    def __init__(self):
        self.cfg = AppConfig()

        # ---------------- Models ----------------
        self.openpose = OpenPoseClient(
            base_url=str(getattr(self.cfg, "openpose_url", "http://127.0.0.1:9001")),
            timeout_s=float(getattr(self.cfg, "openpose_timeout_s", 2.5)),
        )

        self.scorer = ScoreModel(
            keras_path=str(self.cfg.keras_model_path),
            x_scaler_path=str(self.cfg.x_scaler_path),
            y_map_path=str(self.cfg.y_map_path),
        )

        self.exercise_model = ExerciseModelInfer(self.cfg)
        self.ex_T = int(self.exercise_model.T)
        self.ex_F = int(self.exercise_model.F)

        # ---------------- Buffers ----------------
        self.feat_buffer = deque(maxlen=100)
        self.ex_feat_buffer = deque(maxlen=self.ex_T)

        # ---------------- Session Controls ----------------
        self.threshold: float = 30.0
        self.cooldown_seconds: float = 5.0
        self.last_llm_time: float = 0.0

        self.last_feedback_list: List[str] = []
        self.last_feedback_ts: float = 0.0

        self.language: str = "English"

        self.exercise_name: str = "warming_up"
        self.exercise_confidence: float = 0.0

        # ---------------- RAG + LLM ----------------
        self.rag = RAGStore(
            persist_dir=Path(self.cfg.repo_root) / "rag_db"
        )
        self.llm = GroqLLM()

        # ---------------- Rep Counter ----------------
        self.rep_counter = KimoreRepCounter()

        self.EXERCISE_REP_TARGET = {
            "lifting_of_arms": 10,
            "lateral_trunk_tilt_with_arms_in_extension": 8,
            "trunk_rotation": 10,
            "pelvis_rotation": 10,
            "squat": 12,
            "unknown": 10,
        }

        self.rep_target = 10
        self.sets_total = 3
        self.set_index = 1

        self._prev_feat100 = None

    # -----------------------------------------------------
    # OpenPose BODY_25 → Kimore 100D
    # -----------------------------------------------------
    def _openpose25_to_feature100(self, landmarks_25):

        lm = np.asarray(landmarks_25, dtype=np.float32)

        if lm.shape[0] != 25:
            raise ValueError(f"Expected 25 keypoints, got {lm.shape}")

        xy = lm[:, :2]

        root = xy[8]  # MidHip
        xy = xy - root

        neck = xy[1]
        torso_len = np.linalg.norm(neck)
        if torso_len < 1e-6:
            torso_len = 1.0

        xy = xy / torso_len
        flat = xy.flatten()  # 50D

        feat100 = np.concatenate([flat, flat], axis=0)  # 100D
        return feat100.astype(np.float32)

    # -----------------------------------------------------
    # MAIN PROCESSING
    # -----------------------------------------------------
    def process_frame_dataurl(self, frame_b64: str, language: str = None) -> Dict[str, Any]:

        if language:
            self.language = language

        # ---------------- OpenPose ----------------
        op = self.openpose.infer(frame_b64)

        if op is None:
            return self._no_pose_response()

        landmarks_25 = op
        feat100 = self._openpose25_to_feature100(landmarks_25)

        # motion debug
        if self._prev_feat100 is None:
            delta = 0.0
        else:
            delta = float(np.mean(np.abs(feat100 - self._prev_feat100)))
        self._prev_feat100 = feat100.copy()

        print(f"[PREPROCESS] delta={delta:.6f}")

        # push buffers
        self.feat_buffer.append(feat100)
        self.ex_feat_buffer.append(feat100)

        # ---------------- Exercise Model ----------------
        buf = np.asarray(list(self.ex_feat_buffer), dtype=np.float32)

        if buf.shape[0] < self.ex_T:
            last = buf[-1:]
            pad_n = self.ex_T - buf.shape[0]
            buf = np.concatenate([buf, np.repeat(last, pad_n, axis=0)], axis=0)
        else:
            buf = buf[-self.ex_T:]

        X_ex = buf.reshape(1, self.ex_T, self.ex_F)

        pred = self.exercise_model.predict_window(X_ex, top_k=5, debug=False)

        self.exercise_name = pred.best_label_raw
        self.exercise_confidence = float(pred.confidence)
        self.rep_target = int(self.EXERCISE_REP_TARGET.get(self.exercise_name, 10))

        # ---------------- Score Model ----------------
        feats = np.stack(list(self.feat_buffer), axis=0)
        seq = resample_to_T(feats, int(self.cfg.target_timesteps))
        X_score = seq.reshape(1, seq.shape[0], seq.shape[1])

        score = float(self.scorer.predict_score_0_50(X_score))
        status = "CORRECT" if score >= self.threshold else "WRONG"

        # ---------------- Rep Counter ----------------
        try:
            rep_info = self.rep_counter.update({})
        except TypeError:
            rep_info = self.rep_counter.update(self.exercise_name, {})

        # ---------------- LLM FEEDBACK ----------------
        feedback_list: List[str] = []
        now = time.time()

        if status == "WRONG" and (now - self.last_llm_time) >= self.cooldown_seconds:
            try:
                numeric_summary = (
                    f"exercise={self.exercise_name}, "
                    f"score={score:.2f}/50, status={status}"
                )

                pose_summary = f"delta_motion={delta:.4f}"

                chunks = self.rag.query(
                    query_text=f"How to perform {self.exercise_name}. common mistakes, cues, safety",
                    exercise=self.exercise_name,
                    k=6
                )

                rag_context = "\n\n".join(
                    [f"[{c.source}] {c.text}" for c in chunks]
                )

                feedback_list = self.llm.generate_feedback(
                    exercise_name=self.exercise_name,
                    language=self.language,
                    rag_context=rag_context,
                    numeric_summary=numeric_summary,
                    pose_summary=pose_summary,
                )

                self.last_feedback_list = feedback_list
                self.last_feedback_ts = time.time()

            except Exception as e:
                print("[LLM ERROR]", e)
                feedback_list = [f"LLM error: {type(e).__name__}: {e}"]

            self.last_llm_time = now

        if not feedback_list:
            feedback_list = self.last_feedback_list

        return {
            "frame_score": round(score, 2),
            "form_status": status,
            "llm_feedback": feedback_list,

            "exercise_name": self.exercise_name,
            "exercise_confidence": self.exercise_confidence,
            "exercise_probs": pred.probs,
            "exercise_probs_vector": pred.probs_vector,
            "exercise_topk": pred.topk,

            "rep_count": int(rep_info.get("rep_now", 0)),
            "rep_target": self.rep_target,
            "set_index": int(rep_info.get("set_now", 1)),
            "sets_total": int(rep_info.get("set_target", self.sets_total)),
            "rep_info": rep_info,
        }

    # -----------------------------------------------------
    def _no_pose_response(self):
        return {
            "frame_score": 0.0,
            "form_status": "NO_POSE",
            "llm_feedback": ["No person detected"],
            "exercise_name": "no_pose",
            "exercise_confidence": 0.0,
            "exercise_probs": {},
            "exercise_probs_vector": [],
            "exercise_topk": [],
            "rep_count": 0,
            "rep_target": self.rep_target,
            "set_index": self.set_index,
            "sets_total": self.sets_total,
            "rep_info": {},
        }

    # -----------------------------------------------------
    def reset(self, *args, **kwargs):
        self.feat_buffer.clear()
        self.ex_feat_buffer.clear()

        self.exercise_name = "warming_up"
        self.exercise_confidence = 0.0
        self.rep_target = 10
        self.set_index = 1
        self._prev_feat100 = None

        self.last_llm_time = 0.0
        self.last_feedback_list = []

        if self.rep_counter is not None:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()

        print("[PIPELINE] Session reset complete.")