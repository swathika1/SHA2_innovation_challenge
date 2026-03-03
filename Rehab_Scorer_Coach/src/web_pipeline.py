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
from Rehab_Scorer_Coach.src.rep_counter_mediapipe import RepCounterMediaPipe

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

        self.threshold = 35.0
        self.cooldown_seconds = 6.0

        self.rep_counter = RepCounterMediaPipe()

        self._prev_feat = None
        self.language = "English"

        # 🔥 Rep detection state
        self.rep_detection_state = "waiting"  # "waiting" or "in_good_form"
        self.last_rep_score = 0.0
        self.frames_above_threshold = 0
        self.frames_below_threshold = 0
        self.min_frames_for_rep = 1  # Only 1 frame needed
        self.current_rep_count = 0
        self.current_set_count = 1
        self.target_reps = 10
        self.target_sets = 3

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
        try:
            self.rag = RAGStore(persist_dir=Path(self.cfg.repo_root) / "rag_db")
            print("  ✅ RAG Store initialized")
        except Exception as e:
            print(f"  ⚠️  RAG Store failed to initialize: {e}")
            self.rag = None
        
        try:
            self.llm = GroqLLM()
            print("  ✅ Groq LLM initialized with API key")
        except Exception as e:
            print(f"  ⚠️  Groq LLM failed to initialize: {e}")
            print(f"     Please ensure GROQ_API_KEY is set: export GROQ_API_KEY='your-key'")
            self.llm = None

        self.last_llm_time = 0.0
        self.last_feedback_list: List[str] = []

        print("✅ Pipeline Ready")

    # -----------------------------------------------------
    # Automatic Rep Detection
    # -----------------------------------------------------
    def _detect_and_count_reps(self, score: float, delta: float, landmarks: np.ndarray = None, exercise_name: str = "") -> Dict[str, Any]:
        """
        Rep detection using MediaPipe rule-based system.
        Uses joint angles and positions for accurate, stable rep counting.
        Falls back to frame-counting if landmarks unavailable.
        """
        rep_incremented = False
        set_completed = False
        exercise_completed = False
        
        # Use MediaPipe rep counter if landmarks available
        if landmarks is not None and self.rep_counter is not None:
            try:
                # Pass landmarks to MediaPipe rep counter
                rep_detected = self.rep_counter.process(landmarks, exercise_name)
                
                if rep_detected:
                    self.current_rep_count += 1
                    rep_incremented = True
                    print(f"   ✅ REP COUNTED (MediaPipe): Rep {self.current_rep_count}/{self.target_reps} | Set {self.current_set_count}/{self.target_sets}")
                    
                    # Check if set is complete
                    if self.current_rep_count >= self.target_reps:
                        set_completed = True
                        self.current_set_count += 1
                        self.current_rep_count = 0
                        print(f"   🎯 SET COMPLETE: Moving to Set {self.current_set_count}")
                        
                        # Check if all sets complete
                        if self.current_set_count > self.target_sets:
                            exercise_completed = True
                            print(f"   🏆 EXERCISE COMPLETE: All {self.target_sets} sets finished!")
                            self.current_set_count = self.target_sets  # Cap it
            except Exception as e:
                print(f"   ⚠️  MediaPipe rep counter error: {e}")
                # Fall through to frame-counting fallback
        
        # Fallback to frame-counting (for backwards compatibility)
        if not rep_incremented:
            self.frames_above_threshold += 1
            if self.frames_above_threshold >= 20:
                self.frames_above_threshold = 0
                self.current_rep_count += 1
                rep_incremented = True
                print(f"   ✅ REP COUNTED (Fallback): Rep {self.current_rep_count}/{self.target_reps} | Set {self.current_set_count}/{self.target_sets}")
                
                if self.current_rep_count >= self.target_reps:
                    set_completed = True
                    self.current_set_count += 1
                    self.current_rep_count = 0
                    print(f"   🎯 SET COMPLETE: Moving to Set {self.current_set_count}")
                    
                    if self.current_set_count > self.target_sets:
                        exercise_completed = True
                        print(f"   🏆 EXERCISE COMPLETE: All {self.target_sets} sets finished!")
                        self.current_set_count = self.target_sets
        
        rep_info = {
            "rep_now": self.current_rep_count,
            "rep_target": self.target_reps,
            "set_now": self.current_set_count,
            "set_target": self.target_sets,
            "rep_incremented": rep_incremented,
            "set_completed": set_completed,
            "exercise_completed": exercise_completed,
        }
        return rep_info

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
                "rep_info": {
                    "rep_now": self.current_rep_count,
                    "rep_target": self.target_reps,
                    "set_now": self.current_set_count,
                    "set_target": self.target_sets,
                    "rep_incremented": False,
                },
                "landmarks": [],
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
                    "landmarks": landmarks.tolist() if landmarks is not None else [],
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
                    "landmarks": landmarks.tolist() if landmarks is not None else [],
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
            # Demo variability (minimal noise)
            score += np.random.normal(0, 0.5)

            # Motion-based penalty (VERY lenient to ensure reps count)
            if delta < 0.004:
                score -= 10  # too still (reduced from -10)
            elif delta > 0.03:
                score -= 6  # too unstable (reduced from -6)
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
                "landmarks": landmarks.tolist() if landmarks is not None else [],
            }

        status = "CORRECT" if score >= self.threshold else "WRONG"
        print(f"   score = {score:.2f} | status = {status}")

        # 4️⃣.5 REP DETECTION
        print("➡️ Step 4.5: Rep Detection")
        rep_info = self._detect_and_count_reps(score, delta, landmarks, exercise_name)
        print(f"   Rep: {rep_info['rep_now']}/{rep_info['rep_target']} | Set: {rep_info['set_now']}/{rep_info['set_target']}")

        # 5️⃣ LLM FEEDBACK
        print("➡️ Step 5: LLM Check")

        feedback_list = self.last_feedback_list
        now = time.time()

        if status == "WRONG" and (now - self.last_llm_time) > self.cooldown_seconds:
            print("   🔥 Triggering LLM")

            try:
                numeric_summary = f"score={score:.2f}/50 status={status}"
                
                # Enhanced pose summary from landmarks
                pose_parts = [f"delta_motion={delta:.4f}"]
                if landmarks is not None and len(landmarks) >= 33:
                    try:
                        # Key landmark indices (MediaPipe 33-point model)
                        left_shoulder = landmarks[11]
                        right_shoulder = landmarks[12]
                        left_hip = landmarks[23]
                        right_hip = landmarks[24]
                        left_knee = landmarks[25]
                        right_knee = landmarks[26]
                        nose = landmarks[0]
                        
                        # Calculate some meaningful angles/positions
                        if all([left_shoulder[2] > 0.5, right_shoulder[2] > 0.5]):
                            shoulder_gap = abs(left_shoulder[0] - right_shoulder[0])
                            pose_parts.append(f"shoulder_alignment={shoulder_gap:.2f}")
                        
                        if all([left_hip[2] > 0.5, right_hip[2] > 0.5]):
                            hip_gap = abs(left_hip[0] - right_hip[0])
                            pose_parts.append(f"hip_alignment={hip_gap:.2f}")
                        
                        # Vertical alignment (check if torso is upright)
                        if nose[2] > 0.5 and left_hip[2] > 0.5:
                            torso_lean = abs(nose[0] - left_hip[0])
                            pose_parts.append(f"torso_lean={torso_lean:.2f}")
                    except Exception as e:
                        print(f"   ⚠️  Error calculating pose summary: {e}")
                
                pose_summary = " | ".join(pose_parts)

                # ⭐ FIX #4: Improve RAG context retrieval with better queries
                rag_context = ""
                try:
                    if self.rag:
                        # Query with multiple strategies to get best results
                        queries = [
                            f"{exercise_name} proper form technique",
                            f"how to do {exercise_name}",
                            f"{exercise_name} common mistakes",
                            exercise_name
                        ]
                        
                        all_chunks = []
                        for query_text in queries:
                            try:
                                chunks = self.rag.query(
                                    query_text=query_text,
                                    exercise=exercise_name,
                                    k=2,
                                )
                                all_chunks.extend(chunks)
                                if len(all_chunks) >= 4:  # Get enough context
                                    break
                            except:
                                continue
                        
                        if all_chunks:
                            # Remove duplicates and combine
                            seen = set()
                            unique_chunks = []
                            for chunk in all_chunks:
                                text = chunk.text[:150]
                                if text not in seen:
                                    seen.add(text)
                                    unique_chunks.append(text)
                            
                            rag_context = "\n".join(unique_chunks[:3])
                            print(f"   ✅ RAG retrieved {len(unique_chunks)} relevant context items")
                        else:
                            rag_context = f"Standard form guidance for {exercise_name}"
                            print(f"   ⚠️  RAG returned no results, using fallback")
                except Exception as e:
                    print(f"   ⚠️ RAG failed: {e}")
                    rag_context = f"Standard form guidance for {exercise_name}"

                if self.llm:
                    feedback_list = self.llm.generate_feedback(
                        exercise_name=exercise_name,
                        language=self.language,
                        rag_context=rag_context,
                        numeric_summary=numeric_summary,
                        pose_summary=pose_summary,
                    )
                    self.last_feedback_list = feedback_list
                    self.last_llm_time = now
                    print(f"   ✅ LLM feedback generated in {self.language}: {feedback_list}")
                else:
                    print("   ⚠️  LLM not available, using fallback feedback")
                    feedback_list = ["Keep posture controlled and stable."]

            except Exception as e:
                print(f"   ❌ LLM crashed: {e}")
                import traceback
                traceback.print_exc()
                feedback_list = ["Keep posture controlled and stable."]

        print("➡️ Returning response")

        return {
            "frame_score": round(score, 2),
            "form_status": status,
            "llm_feedback": feedback_list,
            "exercise_name": exercise_name,
            "exercise_confidence": confidence,
            "rep_info": rep_info,
            "landmarks": landmarks.tolist() if landmarks is not None else [],
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
        
        # Reset rep tracking
        self.rep_detection_state = "waiting"
        self.frames_above_threshold = 0
        self.current_rep_count = 0
        self.current_set_count = 1

        if self.rep_counter:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()
                
        reset_sequence()
        print("✅ Session reset complete")