import contextlib
from pathlib import Path
from typing import Dict, Any, List
import time
import numpy as np
import cv2
import base64
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import mediapipe_compat as mp  # Tasks-API shim for MediaPipe 0.10.x (mp.solutions.pose)

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
        self.cooldown_seconds = 10.0   # LLM feedback every 10s (fires for ALL form statuses)

        self.rep_counter = RepCounterMediaPipe()

        self._prev_feat = None
        self.language = "English"

        # Rep tracking — time-based for Kimore (every 3-4 seconds)
        self.current_rep_count = 0
        self.current_set_count = 1
        self.target_reps = 10
        self.target_sets = 3
        self.rep_scores_buffer = []
        self.min_motion_for_rep = 0.0045  # used by jitter floor learning
        self.dynamic_min_motion_for_rep = self.min_motion_for_rep

        # Kimore time-based rep interval (3-4 seconds)
        self.rep_interval_seconds = 3.5   # count a rep every 3.5 seconds
        self.last_rep_time = 0.0          # timestamp of last counted rep
        self.active_motion_seconds = 0.0  # accumulated active (non-idle, CORRECT) time

        # Motion + idle stabilization
        self.motion_ema = 0.0
        self.motion_alpha = 0.2
        self.idle_frames = 0
        self.min_idle_seconds = 3.0
        self.min_idle_frames = 15  # updated dynamically from FPS
        self.idle_motion_threshold = 0.0038
        self.motion_floor_ema = self.idle_motion_threshold
        self.dynamic_idle_motion_threshold = self.idle_motion_threshold

        # Live FPS estimation for adaptive timing
        self.frame_fps_ema = 5.0
        self.fps_alpha = 0.15
        self.last_frame_time = 0.0

        # Score — simple EMA, no complex buffering
        self.smoothed_score = 0.0
        self.score_ema_alpha = 0.5   # responsive: each new score has 50% weight

        # Score aggregation — same as Keraal: median of last 20 entries for stable display
        from collections import deque
        self.score_history = deque(maxlen=100)

        # 🔥 MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,           # Lite model — ~3x faster
            enable_segmentation=False,    # Not needed, saves GPU time
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

    # Minimum score (out of 50) to allow the rep timer to advance.
    # Lower than the display threshold (35) so reps count when the
    # person is genuinely exercising even if the model under-scores.
    REP_SCORE_GATE = 12.0

    # -----------------------------------------------------
    # Automatic Rep Detection (Kimore: time-based, every 3-4 seconds)
    # -----------------------------------------------------
    def _detect_and_count_reps(self, score: float, delta: float, landmarks: np.ndarray = None, exercise_name: str = "", form_status: str = "WRONG") -> Dict[str, Any]:
        """
        Kimore rep detection — TIME-BASED approach:
        Increment rep count every 3.5 seconds of ACTIVE exercise time.
        A rep is only counted when ALL conditions are met:
          1. At least 3.5 seconds of active time since the last rep
          2. Person is NOT idle  (sufficient motion detected)
          3. Score >= REP_SCORE_GATE  (person is at least trying)

        Timer PAUSES (does not reset) when idle or score too low,
        and resumes from where it left off once conditions are met.
        """
        rep_incremented = False
        set_completed = False
        exercise_completed = False
        rep_score = None

        # Accumulate scores for per-rep average
        self.rep_scores_buffer.append(score)

        now = time.time()

        # ── IDLE GUARD: don't advance timer when person is not moving ──
        is_idle = self.motion_ema < self.dynamic_idle_motion_threshold
        if is_idle:
            # Pause timer by pushing last_rep_time forward
            if self.last_rep_time > 0.0:
                self.last_rep_time = now  # freeze elapsed at 0
            print(f"      [REP-KIMORE] idle (motion_ema={self.motion_ema:.6f}) — timer paused")
            return {
                "rep_now": self.current_rep_count,
                "rep_target": self.target_reps,
                "set_now": self.current_set_count,
                "set_target": self.target_sets,
                "rep_incremented": False,
                "set_completed": False,
                "exercise_completed": False,
                "rep_score": None,
            }

        # ── SOFT SCORE GATE: pause timer when score is very low ──
        if score < self.REP_SCORE_GATE:
            if self.last_rep_time > 0.0:
                self.last_rep_time = now  # freeze elapsed at 0
            print(f"      [REP-KIMORE] score={score:.1f} < {self.REP_SCORE_GATE} — timer paused")
            return {
                "rep_now": self.current_rep_count,
                "rep_target": self.target_reps,
                "set_now": self.current_set_count,
                "set_target": self.target_sets,
                "rep_incremented": False,
                "set_completed": False,
                "exercise_completed": False,
                "rep_score": None,
            }

        # ── TIME-BASED REP: count a rep every 3-4 seconds of active exercise ──
        # Initialize timer on first active frame
        if self.last_rep_time == 0.0:
            self.last_rep_time = now

        elapsed = now - self.last_rep_time
        if elapsed >= self.rep_interval_seconds:
            self.current_rep_count += 1
            rep_incremented = True
            rep_score = round(float(np.mean(self.rep_scores_buffer)), 2) if self.rep_scores_buffer else round(score, 2)
            self.rep_scores_buffer = []
            self.last_rep_time = now
            print(f"   REP #{self.current_rep_count}/{self.target_reps} | Set {self.current_set_count}/{self.target_sets} | Score: {rep_score} (time-based, {elapsed:.1f}s)")

            if self.current_rep_count >= self.target_reps:
                set_completed = True
                self.current_set_count += 1
                self.current_rep_count = 0
                print(f"   SET COMPLETE -> Set {self.current_set_count}")
                if self.current_set_count > self.target_sets:
                    exercise_completed = True
                    self.current_set_count = self.target_sets

        return {
            "rep_now": self.current_rep_count,
            "rep_target": self.target_reps,
            "set_now": self.current_set_count,
            "set_target": self.target_sets,
            "rep_incremented": rep_incremented,
            "set_completed": set_completed,
            "exercise_completed": exercise_completed,
            "rep_score": rep_score,
        }

    # -----------------------------------------------------
    # Biomechanics — Asymmetry & ROM
    # -----------------------------------------------------
    @staticmethod
    def _angle_3pts(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """Return the interior angle at point b (degrees), using xy only."""
        v1 = a[:2] - b[:2]
        v2 = c[:2] - b[:2]
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            return 180.0
        cos = np.dot(v1, v2) / (n1 * n2)
        return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))

    @staticmethod
    def _compute_biomechanics(landmarks: np.ndarray) -> dict:
        """
        Compute per-frame asymmetry and primary joint angle from 33 MediaPipe landmarks.

        MediaPipe indices used:
          11 left_shoulder  | 12 right_shoulder
          23 left_hip       | 24 right_hip
          25 left_knee      | 26 right_knee
          27 left_ankle     | 28 right_ankle

        Returns
        -------
        dict with:
          asymmetry_pct : float  — |left_knee_angle - right_knee_angle| / avg * 100
          joint_angle   : float  — average knee angle this frame (proxy for ROM depth)
        """
        result = {"asymmetry_pct": None, "joint_angle": None}
        if landmarks is None or len(landmarks) < 29:
            return result

        lhip  = landmarks[23]
        rhip  = landmarks[24]
        lknee = landmarks[25]
        rknee = landmarks[26]
        lank  = landmarks[27]
        rank  = landmarks[28]

        # Visibility guard (z coord used as confidence proxy in mp.solutions.pose)
        l_vis = min(lhip[2], lknee[2], lank[2])
        r_vis = min(rhip[2], rknee[2], rank[2])

        l_angle = WebRehabPipeline._angle_3pts(lhip, lknee, lank) if l_vis > 0.3 else None
        r_angle = WebRehabPipeline._angle_3pts(rhip, rknee, rank) if r_vis > 0.3 else None

        if l_angle is not None and r_angle is not None:
            avg = (l_angle + r_angle) / 2.0
            result["asymmetry_pct"] = round(abs(l_angle - r_angle) / (avg + 1e-6) * 100, 2)
            result["joint_angle"]   = round(avg, 2)
        elif l_angle is not None:
            result["joint_angle"] = round(l_angle, 2)
        elif r_angle is not None:
            result["joint_angle"] = round(r_angle, 2)

        return result

    # -----------------------------------------------------
    # Score aggregation (same as Keraal)
    # -----------------------------------------------------
    def _get_aggregated_score(self) -> float:
        """Median of last ~20 scores (~4 seconds at 5 FPS). Stable for display."""
        if not self.score_history:
            return 0.0
        recent = list(self.score_history)[-20:]
        return float(np.median(recent))

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

            # Downscale to 480p for faster MediaPipe processing
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640.0 / w
                frame_small = cv2.resize(frame, (640, int(h * scale)))
            else:
                frame_small = frame

            image_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
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
    
    def process_frame_dataurl(self, frame_b64: str, language: str = None,mode: str = "auto",manual_exercise: str = None, exercise_hint: str = "") -> Dict[str, Any]:

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

        now_frame = time.time()
        if self.last_frame_time > 0.0:
            dt = max(1e-3, now_frame - self.last_frame_time)
            inst_fps = float(np.clip(1.0 / dt, 2.0, 30.0))
            self.frame_fps_ema = (self.fps_alpha * inst_fps) + ((1.0 - self.fps_alpha) * self.frame_fps_ema)
        self.last_frame_time = now_frame

        self._prev_feat = feature_50d.copy()

        # Learn camera-specific jitter floor during low-motion segments
        if delta < (self.min_motion_for_rep * 1.2):
            self.motion_floor_ema = (0.1 * delta) + (0.9 * self.motion_floor_ema)

        self.dynamic_idle_motion_threshold = max(self.idle_motion_threshold, self.motion_floor_ema * 1.35)
        self.dynamic_min_motion_for_rep = max(self.min_motion_for_rep, self.motion_floor_ema * 1.8)
        self.min_idle_frames = max(8, int(self.min_idle_seconds * self.frame_fps_ema))

        self.motion_ema = (self.motion_alpha * delta) + ((1.0 - self.motion_alpha) * self.motion_ema)
        if self.motion_ema < self.dynamic_idle_motion_threshold:
            self.idle_frames += 1
        else:
            self.idle_frames = 0
        print(f"   delta motion = {delta:.6f} | fps≈{self.frame_fps_ema:.1f} | idle_th={self.dynamic_idle_motion_threshold:.6f} | rep_th={self.dynamic_min_motion_for_rep:.6f}")

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
            
            # ⭐ Use exercise_hint when ML confidence is low
            if exercise_hint and confidence < 0.7:
                exercise_name = exercise_hint
                print(f"   ⭐ Overriding with exercise_hint: {exercise_hint} (ML confidence {confidence:.2f} < 0.7)")
        
        # ⭐ Determine the feedback exercise name (for RAG/LLM queries)
        # This ensures feedback is for the correct exercise the user selected
        feedback_exercise = exercise_hint if exercise_hint else exercise_name
        #exercise_name, confidence = predict_exercise(frame)
        #print(f"   exercise = {exercise_name} ({confidence:.3f})")

        # 4️⃣ SCORE MODEL (100-frame internal buffer)
        print("➡️ Step 4: Score Model")

        score = predict_score(feature_50d)
        if score is not None:
            score = max(0.0, min(float(score), 50.0))

            # Simple EMA — score updates EVERY frame, no clamping, no buffering
            self.smoothed_score = (
                self.score_ema_alpha * score +
                (1.0 - self.score_ema_alpha) * self.smoothed_score
            )
            self.smoothed_score = max(0.0, min(self.smoothed_score, 50.0))
            score = self.smoothed_score
            
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

        if self.idle_frames >= self.min_idle_frames:
            print(f"   ⏸️ IDLE DETECTED: motion_ema={self.motion_ema:.6f}")
            return {
                "frame_score": round(score, 2),
                "form_status": "IDLE",
                "llm_feedback": [],
                "exercise_name": "idle",
                "exercise_confidence": confidence,
                "rep_info": {
                    "rep_now": self.current_rep_count,
                    "rep_target": self.target_reps,
                    "set_now": self.current_set_count,
                    "set_target": self.target_sets,
                    "rep_incremented": False,
                    "set_completed": False,
                    "exercise_completed": False,
                    "rep_score": None,
                },
                "landmarks": landmarks.tolist() if landmarks is not None else [],
            }

        status = "CORRECT" if score >= self.threshold else "WRONG"
        print(f"   score = {score:.2f} | status = {status}")

        # 4️⃣.5 REP DETECTION
        print("➡️ Step 4.5: Rep Detection")
        rep_info = self._detect_and_count_reps(score, delta, landmarks, feedback_exercise, form_status=status)
        print(f"   Rep: {rep_info['rep_now']}/{rep_info['rep_target']} | Set: {rep_info['set_now']}/{rep_info['set_target']}")

        # 4️⃣.6 SCORE AGGREGATION (same as Keraal)
        self.score_history.append(score)
        aggregated_score = self._get_aggregated_score()
        print(f"   Aggregated score: {aggregated_score:.2f}/50")

        # 4️⃣.7 BIOMECHANICS — asymmetry & ROM
        biomechanics = self._compute_biomechanics(landmarks)
        print(f"   Biomechanics: asymmetry={biomechanics['asymmetry_pct']}% | joint_angle={biomechanics['joint_angle']}°")

        # 5️⃣ LLM FEEDBACK (enabled for ALL form statuses — CORRECT and WRONG)
        print("➡️ Step 5: LLM Check")

        feedback_list = self.last_feedback_list
        now = time.time()

        if (now - self.last_llm_time) > self.cooldown_seconds:
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
                        # Use feedback_exercise for accurate RAG retrieval
                        queries = [
                            f"{feedback_exercise} proper form technique",
                            f"how to do {feedback_exercise}",
                            f"{feedback_exercise} common mistakes",
                            feedback_exercise
                        ]
                        
                        all_chunks = []
                        for query_text in queries:
                            try:
                                chunks = self.rag.query(
                                    query_text=query_text,
                                    exercise=feedback_exercise,
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
                            rag_context = f"Standard form guidance for {feedback_exercise}"
                            print(f"   ⚠️  RAG returned no results, using fallback")
                except Exception as e:
                    print(f"   ⚠️ RAG failed: {e}")
                    rag_context = f"Standard form guidance for {feedback_exercise}"

                if self.llm:
                    feedback_list = self.llm.generate_feedback(
                        exercise_name=feedback_exercise,
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
            "aggregated_score": round(aggregated_score, 2),
            "rep_info": rep_info,
            "landmarks": landmarks.tolist() if landmarks is not None else [],
            "asymmetry_pct": biomechanics["asymmetry_pct"],
            "joint_angle": biomechanics["joint_angle"],
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
        self.current_rep_count = 0
        self.current_set_count = 1
        self.rep_scores_buffer = []
        self.motion_ema = 0.0
        self.idle_frames = 0
        self.smoothed_score = 0.0
        self.motion_floor_ema = self.idle_motion_threshold
        self.dynamic_idle_motion_threshold = self.idle_motion_threshold
        self.dynamic_min_motion_for_rep = self.min_motion_for_rep
        self.frame_fps_ema = 5.0
        self.last_frame_time = 0.0
        self.last_rep_time = 0.0  # reset time-based rep timer
        self.score_history.clear()

        if self.rep_counter:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()
                
        reset_sequence()
        print("✅ Session reset complete")