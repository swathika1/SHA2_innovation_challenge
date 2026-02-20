import contextlib
from pathlib import Path
from typing import Dict, Any, List
import time
import numpy as np
import cv2
import base64
import mediapipe as mp

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.rag_store import RAGStore
from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
from Rehab_Scorer_Coach.src.rep_counter_kimore import KimoreRepCounter

# 🔥 MODEL LOADER (50D + 100-frame scoring)
from Rehab_Scorer_Coach.src.models_loader import (
    normalize_pose_xy,
    to_50d,
    predict_exercise,
    predict_score,
    reset_sequence
)


class WebRehabPipeline:
    def __init__(self):
        print("🚀 Initializing WebRehabPipeline")

        self.cfg = AppConfig()

        self.threshold=35.0 #30.0
        self.cooldown_seconds = 6.0

        self.rep_counter = KimoreRepCounter()

        self._prev_feat = None
        self.language = "English"

        # 🔥 MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # LLM state
        self.rag = RAGStore(persist_dir=Path(self.cfg.repo_root) / "rag_db")
        self.llm = GroqLLM()

        self.last_llm_time = 0.0
        self.last_feedback_list: List[str] = []

        print("✅ Pipeline Ready")

    # -----------------------------------------------------
    # MediaPipe Pose Extraction
    # -----------------------------------------------------
    def _extract_mediapipe_landmarks(self, frame_b64: str):
        # sourcery skip: class-extract-method, for-append-to-extend
        try:
            header, encoded = frame_b64.split(",", 1)
            frame_data = base64.b64decode(encoded)
            frame_array = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                return None, None

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image_rgb)

            if not results.pose_landmarks:
                return frame, None   # 🔥 return frame but no landmarks

            landmarks = []
            for lm in results.pose_landmarks.landmark:
                landmarks.append([lm.x, lm.y, lm.z])

            return frame, np.array(landmarks, dtype=np.float32)

        except Exception as e:
            print("❌ MediaPipe extraction error:", e)
            return None, None
        
    def _extract_mediapipe_landmarks_old(self, frame_b64: str):
        # sourcery skip: for-append-to-extend, list-comprehension

        try:
            header, encoded = frame_b64.split(",", 1)
            frame_data = base64.b64decode(encoded)
            frame_array = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                return None

            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image_rgb)

            if not results.pose_landmarks:
                return None

            landmarks = []
            for lm in results.pose_landmarks.landmark:
                landmarks.append([lm.x, lm.y, lm.z])

            #return np.array(landmarks, dtype=np.float32)
            return frame, np.array(landmarks, dtype=np.float32)

        except Exception as e:
            print("❌ MediaPipe extraction error:", e)
            return None

    # -----------------------------------------------------
    # Main Frame Processing
    # -----------------------------------------------------
    
    def process_frame_dataurl(self, frame_b64: str, language: str = None,mode: str = "auto",manual_exercise: str = None) -> Dict[str, Any]:

        print("\n================ NEW FRAME ================")

        if language:
            self.language = language

        # 1️⃣ MEDIAPIPE
        print("➡️ Step 1: MediaPipe")
        frame, landmarks = self._extract_mediapipe_landmarks(frame_b64)

        if landmarks is None:
            print("❌ No pose detected")
            return {
                "frame_score": 0.0,
                "form_status": "NO_POSE",
                "llm_feedback": ["No person detected"],
                "exercise_name": "no_pose",
                "exercise_confidence": 0.0,
            }

        # 2️⃣ FEATURE (50D PIPELINE)
        print("➡️ Step 2: Feature build (50D)")

        keypoints_xy = landmarks[:, :2]
        normalized = normalize_pose_xy(keypoints_xy)
        feature_50d = to_50d(normalized)

        if self._prev_feat is None:
            delta = 0.0
        else:
            delta = float(np.mean(np.abs(feature_50d - self._prev_feat)))

        self._prev_feat = feature_50d.copy()
        print(f"   delta motion = {delta:.6f}")

        # 3️⃣ EXERCISE MODEL
        print("➡️ Step 3: Exercise Model")
        print("Raw frame dtype:", frame.dtype)
        print("Raw frame min:", frame.min())
        print("Raw frame max:", frame.max())
        print("Raw frame mean:", frame.mean())
        
        
        # -----------------------------------------------------
        # 2️⃣ EXERCISE MODEL — DIRECT RAW FRAME
        # -----------------------------------------------------
        
        if mode == "manual":
            if manual_exercise is None:
                return {
                    "frame_score": 0.0,
                    "form_status": "NO_EXERCISE_SELECTED",
                    "llm_feedback": ["Please select an exercise"],
                    "exercise_name": "none",
                    "exercise_confidence": 1.0,
                }

            exercise_name = manual_exercise
            confidence = 1.0
            print(f"   MANUAL exercise = {exercise_name}")
        else:
            header, encoded = frame_b64.split(",", 1)
            frame_data = base64.b64decode(encoded)
            frame_array = np.frombuffer(frame_data, np.uint8)
            frame_ex = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame_ex is None:
                return {
                    "frame_score": 0.0,
                    "form_status": "NO_FRAME",
                    "llm_feedback": ["Invalid frame"],
                    "exercise_name": "no_frame",
                    "exercise_confidence": 0.0,
                }

            print("➡️ Step 1: Exercise Model (RAW FRAME)")
            exercise_name, confidence = predict_exercise(frame_ex)
            print(f"   exercise = {exercise_name} ({confidence:.3f})")
        #exercise_name, confidence = predict_exercise(frame)

        #print(f"   exercise = {exercise_name} ({confidence:.3f})")

        # 4️⃣ SCORE MODEL (100-frame internal buffer)
        print("➡️ Step 4: Score Model")

        score = predict_score(feature_50d)
        if score is not None:
            # Demo variability
            score += np.random.normal(0, 2.5)

            # Motion-based penalty
            if delta < 0.004:
                score -= 10  # too still
            elif delta > 0.03:
                score -= 8  # too unstable
            # Clamp
            score = max(0, min(score, 50))
            
        if score is None:
            print("   warming up sequence buffer...")
            return {
                "frame_score": 0.0,
                "form_status": "WARMUP",
                "llm_feedback": [],
                "exercise_name": exercise_name,
                "exercise_confidence": confidence,
            }

        status = "CORRECT" if score >= self.threshold else "WRONG"
        print(f"   score = {score:.2f} | status = {status}")

        # 5️⃣ LLM FEEDBACK
        print("➡️ Step 5: LLM Check")

        feedback_list = self.last_feedback_list
        now = time.time()

        if status == "WRONG" and (now - self.last_llm_time) > self.cooldown_seconds:
            print("   🔥 Triggering LLM")

            try:
                numeric_summary = f"score={score:.2f}/50 status={status}"
                pose_summary = f"delta_motion={delta:.4f}"

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
        }

    # -----------------------------------------------------
    # Reset
    # -----------------------------------------------------
    def reset(self, *args, **kwargs):
        print("🔄 Resetting session")

        reset_sequence()

        self._prev_feat = None
        self.last_feedback_list = []
        self.last_llm_time = 0.0

        if self.rep_counter:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()
                
        reset_sequence()
        print("✅ Session reset complete")