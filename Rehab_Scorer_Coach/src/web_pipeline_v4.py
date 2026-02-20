import contextlib
from collections import deque
from pathlib import Path
from typing import Dict, Any, List
import time
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
        print("🚀 Initializing WebRehabPipeline")

        self.cfg = AppConfig()

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

        self.feat_buffer = deque(maxlen=200)
        self.ex_feat_buffer = deque(maxlen=self.ex_T)

        self.threshold = 30.0
        self.cooldown_seconds = 6.0

        self.rep_counter = KimoreRepCounter()

        self._prev_feat = None
        self.language = "English"

        # LLM state
        self.rag = RAGStore(persist_dir=Path(self.cfg.repo_root) / "rag_db")
        self.llm = GroqLLM()

        self.last_llm_time = 0.0
        self.last_feedback_list: List[str] = []

        print("✅ Pipeline Ready")

    # -----------------------------------------------------
    # OpenPose BODY_25 → 100D Feature
    # -----------------------------------------------------
    def _openpose25_to_feature100(self, landmarks_25):

        lm = np.asarray(landmarks_25, dtype=np.float32)
        xy = lm[:, :2]

        root = xy[8]
        xy = xy - root

        neck = xy[1]
        torso = np.linalg.norm(neck)
        if torso < 1e-6:
            torso = 1.0

        xy = xy / torso
        flat = xy.flatten()
        feat = np.concatenate([flat, flat], axis=0)

        return feat.astype(np.float32)

    # -----------------------------------------------------
    # Main Frame Processing
    # -----------------------------------------------------
    def process_frame_dataurl(self, frame_b64: str, language: str = None) -> Dict[str, Any]:

        print("\n================ NEW FRAME ================")

        if language:
            self.language = language

        # 1️⃣ OPENPOSE
        print("➡️ Step 1: OpenPose")
        op = self.openpose.infer(frame_b64)

        if op is None:
            print("❌ No pose detected")
            return {
                "frame_score": 0.0,
                "form_status": "NO_POSE",
                "llm_feedback": ["No person detected"],
                "exercise_name": "no_pose",
                "exercise_confidence": 0.0,
            }

        # 2️⃣ FEATURE
        print("➡️ Step 2: Feature build")
        feat = self._openpose25_to_feature100(op)

        if self._prev_feat is None:
            delta = 0.0
        else:
            delta = float(np.mean(np.abs(feat - self._prev_feat)))

        self._prev_feat = feat.copy()
        print(f"   delta motion = {delta:.6f}")

        self.feat_buffer.append(feat)
        self.ex_feat_buffer.append(feat)

        # 3️⃣ EXERCISE MODEL
        print("➡️ Step 3: Exercise Model")

        buf = np.asarray(self.ex_feat_buffer, dtype=np.float32)

        if buf.shape[0] < self.ex_T:
            last = buf[-1:]
            pad = np.repeat(last, self.ex_T - buf.shape[0], axis=0)
            buf = np.concatenate([buf, pad], axis=0)
        else:
            buf = buf[-self.ex_T:]

        F = buf.shape[1]
        X_ex = buf.reshape(1, self.ex_T, F)

        pred = self.exercise_model.predict_window(X_ex, top_k=5, debug=False)

        exercise_name = pred.best_label_raw
        confidence = float(pred.confidence)

        print(f"   exercise = {exercise_name} ({confidence:.3f})")

        # 4️⃣ SCORE MODEL
        print("➡️ Step 4: Score Model")

        feats = np.stack(self.feat_buffer, axis=0)
        seq = resample_to_T(feats, int(self.cfg.target_timesteps))

        T_score, F_score = seq.shape
        X_score = seq.reshape(1, T_score, F_score)

        score = float(self.scorer.predict_score_0_50(X_score))
        status = "CORRECT" if score >= self.threshold else "WRONG"

        print(f"   score = {score:.2f} | status = {status}")

        # 5️⃣ LLM FEEDBACK (SAFE)
        print("➡️ Step 5: LLM Check")

        feedback_list = self.last_feedback_list
        now = time.time()

        if status == "WRONG" and (now - self.last_llm_time) > self.cooldown_seconds:
            print("   🔥 Triggering LLM")

            try:
                numeric_summary = f"score={score:.2f}/50 status={status}"
                pose_summary = f"delta_motion={delta:.4f}"

                # RAG SAFE
                try:
                    chunks = self.rag.query(
                        query_text=f"How to perform {exercise_name}. cues",
                        exercise=exercise_name,
                        k=3,
                    )
                    rag_context = "\n".join([c.text[:200] for c in chunks])
                except Exception as e:
                    print("   ⚠️ RAG failed:", e)
                    rag_context = ""

                # LLM CALL
                feedback_list = self.llm.generate_feedback(
                    exercise_name=exercise_name,
                    language=self.language,
                    rag_context=rag_context,
                    numeric_summary=numeric_summary,
                    pose_summary=pose_summary,
                )

                self.last_feedback_list = feedback_list
                self.last_llm_time = now

                print("   ✅ LLM feedback generated")

            except Exception as e:
                print("   ❌ LLM crashed:", e)
                feedback_list = ["Keep posture controlled and stable."]

        print("➡️ Returning response")

        return {
            "frame_score": round(score, 2),
            "form_status": status,
            "llm_feedback": feedback_list,
            "exercise_name": exercise_name,
            "exercise_confidence": confidence,
            "exercise_probs": pred.probs,
            "exercise_topk": pred.topk,
        }

    # -----------------------------------------------------
    # Reset
    # -----------------------------------------------------
    def reset(self, *args, **kwargs):
        print("🔄 Resetting session")

        self.feat_buffer.clear()
        self.ex_feat_buffer.clear()
        self._prev_feat = None
        self.last_feedback_list = []
        self.last_llm_time = 0.0

        if self.rep_counter:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()

        print("✅ Session reset complete")