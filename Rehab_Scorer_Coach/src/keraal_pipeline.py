"""
KERAAL Low Back Pain Rehabilitation Pipeline
Handles BlazePose 33 landmarks with 48-frame rolling window
Exercise classes: "CTK": "Forward Flexion", "ELK": "Flank Stretch", "RTK": "Torso Rotation"
"""

import contextlib
import numpy as np
import cv2
import base64
import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..'))
import mediapipe_compat as mp  # Tasks-API shim for MediaPipe 0.10.x (mp.solutions.pose)
import keras
from collections import deque
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import time

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.rep_counter_mediapipe import RepCounterMediaPipe

# =========================================================

WINDOW_SIZE = 48  # Rolling buffer of 48 frames
NUM_LANDMARKS = 33  # BlazePose
EXERCISE_DETECTION_THRESHOLD = 0.5
CORRECTNESS_THRESHOLD = 0.50  # >= 0.50 = correct  (score >= 25/50)
SCORE_MULTIPLIER = 50  # correctness (0-1) * 50 = raw score (0-50)

# Exercise class mapping
KERAAL_EXERCISE_MAP = {
    "CTK": "Forward Flexion",
    "ELK": "Flank Stretch",
    "RTK": "Torso Rotation",
    "idle": "Idle"
}

KERAAL_EXERCISE_CLASSES = list(KERAAL_EXERCISE_MAP.keys())


# =========================================================
# KERAAL MODELS LOADER
# =========================================================

class KeraalModelsLoader:
    """Loads and manages KERAAL models"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        print("🚀 Loading KERAAL Models...")
        
        cfg = AppConfig()
        models_dir = Path(cfg.repo_root) / "models"
        
        # Load exercise detection model
        exercise_model_path = models_dir / "keraal_exercise_detection.keras"
        self.exercise_model = keras.models.load_model(str(exercise_model_path))
        print(f"✅ Loaded exercise detection model: {exercise_model_path}")
        
        # Load correctness/scoring model
        correctness_model_path = models_dir / "keraal_model_v1.keras"
        self.correctness_model = keras.models.load_model(str(correctness_model_path))
        print(f"✅ Loaded correctness model: {correctness_model_path}")
        
        print("✅ KERAAL Models Ready")


# =========================================================
# LANDMARK NORMALIZATION (KERAAL STYLE WITH VELOCITY)
# =========================================================

FRAME_FEATURES = 198  # 99 position + 99 velocity


def normalize_landmarks_scoring(landmarks: np.ndarray) -> np.ndarray:
    """
    Normalize for SCORING model (keraal_model_v1).
    Hip-center + torso scaling using shoulder-to-hip distance.
    Returns flattened (99,) = 33 joints * 3 coords.
    
    Scaling reference: torso = ||left_shoulder - left_hip|| after centering.
    """
    coords = landmarks.copy()  # (33, 3)
    
    # Hip center normalization
    hip_center = (coords[23] + coords[24]) / 2.0
    coords = coords - hip_center
    
    # Torso scaling: distance from left shoulder to left hip (after centering)
    torso = np.linalg.norm(coords[11] - coords[23])
    if torso > 1e-6:
        coords = coords / torso
    
    return coords.reshape(-1)  # (99,)


def normalize_landmarks_exercise_detection(landmarks: np.ndarray) -> np.ndarray:
    """
    Normalize for EXERCISE DETECTION model (keraal_exercise_detection).
    Hip-center + torso scaling using hip-center-to-shoulder distance.
    Returns (33, 3) array.
    
    Scaling reference: torso_length = ||left_shoulder|| after centering
    (i.e. distance from hip center to left shoulder).
    """
    coords = landmarks.copy()  # (33, 3)
    
    # Hip center normalization
    hip_center = (coords[23] + coords[24]) / 2.0
    coords = coords - hip_center
    
    # Torso scaling: distance from hip center (origin) to left shoulder
    left_shoulder = coords[11]
    torso_length = np.linalg.norm(left_shoulder)
    if torso_length > 1e-6:
        coords = coords / torso_length
    
    return coords  # (33, 3)


# Keep backward-compatible alias
normalize_landmarks_keraal = normalize_landmarks_scoring


# =========================================================
# POSE BUFFER FOR ROLLING WINDOW WITH VELOCITY
# =========================================================

class PoseBuffer:
    """
    Maintains dual rolling buffers for the two KERAAL models:
      - Scoring buffer:  (198,) per frame = 99 position + 99 velocity → (1,48,198)
      - Exercise buffer: (33,3) per frame = exercise-normalized landmarks → (1,48,33,3)
    """
    
    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        # Scoring model buffer (position + velocity)
        self.positions = deque(maxlen=window_size)
        self.prev_frame = None
        # Exercise detection model buffer (just normalized landmarks)
        self.exercise_frames = deque(maxlen=window_size)
    
    def add(self, scoring_frame: np.ndarray, exercise_frame: np.ndarray = None) -> bool:
        """
        Add frames for both models.
        
        Args:
            scoring_frame: (99,) scoring-model-normalized landmarks
            exercise_frame: (33,3) exercise-model-normalized landmarks (optional)
        
        Returns:
            True if frame added successfully
        """
        position = scoring_frame  # (99,)
        
        # Compute velocity for scoring model
        if self.prev_frame is None:
            velocity = np.zeros_like(position)
        else:
            velocity = position - self.prev_frame
        
        self.prev_frame = position.copy()
        
        # Concatenate position + velocity -> (198,)
        frame_features = np.concatenate([position, velocity])
        self.positions.append(frame_features)
        
        # Store exercise-detection frame
        if exercise_frame is not None:
            self.exercise_frames.append(exercise_frame)
        
        return True
    
    def is_full(self) -> bool:
        """Check if buffer is full"""
        return len(self.positions) == self.window_size
    
    def get_sequence(self) -> np.ndarray:
        """Get scoring buffer as (1, 48, 198) for scoring model"""
        if len(self.positions) < self.window_size:
            return None
        seq = np.array(self.positions)  # (48, 198)
        return np.expand_dims(seq, axis=0)  # (1, 48, 198)
    
    def get_exercise_sequence(self) -> np.ndarray:
        """Get exercise buffer as (1, 48, 33, 3) for exercise detection model"""
        if len(self.exercise_frames) < self.window_size:
            return None
        seq = np.array(list(self.exercise_frames))  # (48, 33, 3)
        return np.expand_dims(seq, axis=0)  # (1, 48, 33, 3)
    
    def reset(self) -> None:
        """Clear both buffers"""
        self.positions.clear()
        self.prev_frame = None
        self.exercise_frames.clear()


# =========================================================
# KERAAL PIPELINE
# =========================================================

class KeraalRehabPipeline:
    """
    KERAAL-specific rehabilitation pipeline for low back pain exercises.
    Uses BlazePose 33 landmarks with 48-frame rolling window.
    """
    
    def __init__(self):
        print("🚀 Initializing KeraalRehabPipeline")
        
        self.cfg = AppConfig()
        
        # Load models
        self.models = KeraalModelsLoader()
        
        # MediaPipe Pose (BlazePose)
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,           # Lite model — ~3x faster
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        
        # Pose buffer
        self.pose_buffer = PoseBuffer(window_size=WINDOW_SIZE)
        
        # Rep counter (MediaPipe rule-based)
        self.rep_counter = RepCounterMediaPipe()
        
        # Session state
        self.language = "English"
        self.current_exercise = "idle"
        self.threshold = 25.0  # Score threshold for "CORRECT" display
        self.cooldown_seconds = 6.0
        
        # Idle detection
        self.idle_frames = 0
        self.min_idle_seconds = 4.0
        self.min_idle_frames = 20  # updated dynamically from FPS
        self.idle_motion_threshold = 0.0025
        self.motion_ema = 0.0
        self.motion_alpha = 0.2
        self.last_frame_motion = 0.0
        self.motion_floor_ema = self.idle_motion_threshold
        self.dynamic_idle_motion_threshold = self.idle_motion_threshold

        # Live FPS estimation for adaptive thresholds
        self.frame_fps_ema = 5.0
        self.fps_alpha = 0.15
        self.last_frame_time = 0.0
        
        # Rep tracking — simple, no quality gates
        self.current_rep_count = 0
        self.current_set_count = 1
        self.target_reps = 10
        self.target_sets = 3
        self.rep_scores_buffer = []
        self.min_motion_for_rep = 0.0030  # used by jitter floor learning
        self.dynamic_min_motion_for_rep = self.min_motion_for_rep
        
        # Frame counter for window-level predictions
        self.frame_count = 0
        self.window_predictions = deque(maxlen=5)  # Last 5 window predictions
        
        # Aggregation for 10-second window
        self.score_history = deque(maxlen=100)  # Last 100 scores (at ~10 FPS = 10 sec)
        self.last_llm_feedback_score = None
        self.llm_feedback_cooldown = 0
        
        # Score display gate: only show score every 10-15 seconds (50-75 frames at 5 FPS)
        self.score_display_cooldown = 0
        self.score_display_interval = 60  # frames (12 seconds at 5 FPS = mid-range of 10-15 sec)
        
        # RAG Store for exercise reference knowledge
        self.rag = None
        try:
            from Rehab_Scorer_Coach.src.rag_store import RAGStore
            from pathlib import Path as _Path
            rag_dir = _Path(self.cfg.repo_root) / "rag_db"
            if rag_dir.exists():
                self.rag = RAGStore(persist_dir=rag_dir)
                print("  ✅ KERAAL RAG Store initialized")
            else:
                print(f"  ⚠️  KERAAL RAG: rag_db not found at {rag_dir}")
        except Exception as e:
            print(f"  ⚠️  KERAAL RAG Store failed: {e}")
        
        # Also try FAISS-based rag_engine as fallback
        self._rag_engine_available = False
        try:
            import rag_engine as _re
            self._rag_engine = _re
            self._rag_engine_available = True
            print("  ✅ KERAAL rag_engine (FAISS) available")
        except Exception:
            self._rag_engine = None
        
        print("✅ KeraalRehabPipeline Ready")
    
    
    def _extract_mediapipe_landmarks_keraal(self, frame_b64: str) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Extract BlazePose 33 landmarks from frame.
        
        Args:
            frame_b64: Base64 encoded frame with data URL prefix
        
        Returns:
            (frame_bgr, landmarks_33x3) or (None, None)
        """
        try:
            # Decode base64
            header, encoded = frame_b64.split(",", 1)
            frame_data = base64.b64decode(encoded)
            frame_array = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            
            if frame is None:
                print("❌ Failed to decode frame")
                return None, None
            
            # Downscale to 480p for faster MediaPipe processing
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640.0 / w
                frame_small = cv2.resize(frame, (640, int(h * scale)))
            else:
                frame_small = frame

            # Convert BGR to RGB for MediaPipe
            image_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image_rgb)
            
            if not results.pose_landmarks:
                print("❌ No pose detected")
                return frame, None
            
            # Extract 33 landmarks as (33, 3)
            landmarks = np.array([
                [lm.x, lm.y, lm.z]
                for lm in results.pose_landmarks.landmark
            ], dtype=np.float32)
            
            return frame, landmarks
        
        except Exception as e:
            print(f"❌ MediaPipe extraction error: {e}")
            return None, None
    
    
    def _predict_exercise_detection(self, landmarks_seq: np.ndarray) -> Tuple[str, float]:
        """
        Predict exercise from normalized landmarks using exercise detection model.
        
        Args:
            landmarks_seq: (48, 33, 3) sequence of landmarks OR (1, 48, 33, 3) batched
        
        Returns:
            (exercise_name, confidence)
        """
        try:
            # Ensure input is (1, 48, 33, 3)
            if len(landmarks_seq.shape) == 3:
                # If (48, 33, 3), add batch dimension
                input_seq = np.expand_dims(landmarks_seq, axis=0)
            else:
                input_seq = landmarks_seq
            
            print(f"   Exercise model input shape: {input_seq.shape}")
            
            # Predict
            probs = self.models.exercise_model.predict(input_seq, verbose=0)[0]
            class_idx = int(np.argmax(probs))
            confidence = float(probs[class_idx])
            
            # Map to class name
            exercise_name = KERAAL_EXERCISE_CLASSES[class_idx] if class_idx < len(KERAAL_EXERCISE_CLASSES) else "idle"
            exercise_display = KERAAL_EXERCISE_MAP.get(exercise_name, exercise_name)
            
            print(f"   Exercise: {exercise_display} (conf={confidence:.3f})")
            
            return exercise_name, confidence
        
        except Exception as e:
            print(f"❌ Exercise detection error: {e}")
            import traceback
            traceback.print_exc()
            return "idle", 0.0
    
    
    def _predict_correctness(self, sequence: np.ndarray) -> float:
        """
        Predict correctness score (0-1) from window sequence.
        
        Args:
            sequence: (1, 48, 198) sequence with position + velocity features
        
        Returns:
            correctness_score (0-1)
        """
        try:
            # Verify shape is correct: (1, 48, 198)
            if sequence.shape != (1, WINDOW_SIZE, FRAME_FEATURES):
                print(f"⚠️ Unexpected shape: {sequence.shape}, expected (1, {WINDOW_SIZE}, {FRAME_FEATURES})")
                return 0.0
            
            print(f"   Predicting correctness from shape: {sequence.shape}")
            
            # Predict
            score = self.models.correctness_model.predict(sequence, verbose=0)[0][0]
            score = float(np.clip(score, 0.0, 1.0))
            
            return score
        
        except Exception as e:
            print(f"❌ Correctness prediction error: {e}")
            print(f"   Sequence shape: {sequence.shape if sequence is not None else 'None'}")
            return 0.0
    
    
    def _determine_form_status(self, correctness: float) -> str:
        """Determine form status based on correctness threshold"""
        return "CORRECT" if correctness >= CORRECTNESS_THRESHOLD else "INCORRECT"
    
    
    def _get_aggregated_score(self) -> float:
        """
        Get score from the most recent ~4 seconds of predictions.
        Uses the last 20 entries (at ~5 FPS ≈ 4 seconds) so the
        displayed score actually responds to what the patient is doing
        *right now* instead of being diluted by old history.
        """
        if not self.score_history:
            return 0.0
        recent = list(self.score_history)[-20:]  # last ~4 seconds
        return float(np.median(recent))           # median resists outliers
    
    
    def _generate_llm_feedback(self, form_status: str, aggregated_score: float, exercise_name: str, landmarks: np.ndarray = None) -> List[str]:
        """
        Generate REAL LLM feedback for KERAAL exercises in selected language.
        ONLY called when form is INCORRECT.
        Uses Groq LLM with language support.
        Returns list of feedback strings.
        """
        feedback = []
        
        # ONLY generate feedback when form is INCORRECT
        if form_status != "INCORRECT":
            return feedback  # Return empty for correct form
        
        # Cooldown: only generate feedback every 10-15 seconds
        self.llm_feedback_cooldown -= 1
        if self.llm_feedback_cooldown > 0:
            return feedback
        
        try:
            # Build LLM prompt with language requirement
            score_quality = "very poor" if aggregated_score < 10 else "poor" if aggregated_score < 20 else "needs improvement" if aggregated_score < 35 else "almost correct"
            
            language = getattr(self, 'language', 'English')
            
            prompt = f"""You are an expert physical therapy coach. Respond ENTIRELY in {language}.

Exercise: {exercise_name}

Patient Performance:
- Form Score: {aggregated_score:.1f}/50 ({score_quality})
- Status: INCORRECT form detected

Provide 2-3 SHORT, specific sentences (under 30 words each) in {language} that:
1. Identify the specific problem area
2. Explain the exact correction needed

CRITICAL: Respond ONLY in {language}. Do NOT use any other language."""

            # Use Groq LLM
            try:
                from Rehab_Scorer_Coach.src.llm_groq import GroqLLM
                llm = GroqLLM()
                
                # Enhanced pose summary from landmarks
                pose_parts = []
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
                
                pose_summary = " | ".join(pose_parts) if pose_parts else ""
                
                # Retrieve RAG context for this exercise
                rag_context = ""
                try:
                    # Try ChromaDB RAG store first
                    if self.rag:
                        queries = [
                            f"{exercise_name} proper form technique",
                            f"{exercise_name} common mistakes corrections",
                            exercise_name
                        ]
                        all_chunks = []
                        for q in queries:
                            try:
                                chunks = self.rag.query(query_text=q, exercise=exercise_name, k=2)
                                all_chunks.extend(chunks)
                                if len(all_chunks) >= 4:
                                    break
                            except Exception:
                                continue
                        if all_chunks:
                            seen = set()
                            unique = []
                            for c in all_chunks:
                                t = c.text[:200]
                                if t not in seen:
                                    seen.add(t)
                                    unique.append(t)
                            rag_context = "\n".join(unique[:3])
                            print(f"   ✅ KERAAL RAG (ChromaDB): {len(unique)} chunks for {exercise_name}")
                    
                    # Fallback to FAISS rag_engine
                    if not rag_context and self._rag_engine_available:
                        rag_context = self._rag_engine.retrieve(
                            f"{exercise_name} form technique corrections",
                            top_k=3,
                            source_filter="keraal"
                        )
                        if not rag_context:
                            # Try without source filter
                            rag_context = self._rag_engine.retrieve(f"{exercise_name} form", top_k=3)
                        if rag_context:
                            print(f"   ✅ KERAAL RAG (FAISS): retrieved context for {exercise_name}")
                except Exception as rag_err:
                    print(f"   ⚠️  KERAAL RAG retrieval failed: {rag_err}")
                    rag_context = ""
                
                if not rag_context:
                    rag_context = f"Standard rehabilitation guidance for {exercise_name}: Maintain proper alignment, move slowly and controlled, avoid compensatory movements."
                    print(f"   ℹ️  Using fallback RAG context for {exercise_name}")
                
                feedback = llm.generate_feedback(
                    exercise_name=exercise_name,
                    language=language,
                    rag_context=rag_context,
                    numeric_summary=f"score={aggregated_score:.1f}/50",
                    pose_summary=pose_summary
                )
                print(f"✅ LLM feedback in {language} (RAG-enhanced): {feedback}")
            except Exception as e:
                print(f"⚠️  LLM failed: {e}")
                # Fallback feedback
                if aggregated_score < 15:
                    feedback = ["Focus on proper form.", "Move slowly and controlled.", "Try again."]
                elif aggregated_score < 27:
                    feedback = ["Adjust your positioning.", "Small corrections matter.", "Try once more."]
                else:
                    feedback = ["Almost there!", "Fine-tune your form.", "One more perfect rep!"]
            
            # Filter and limit feedback
            feedback = [f for f in feedback if f and isinstance(f, str)][:3]
            
            # Reset cooldown (12 seconds at 5 FPS)
            self.llm_feedback_cooldown = 60
            
        except Exception as e:
            print(f"❌ Feedback generation error: {e}")
            feedback = []
        
        return feedback
    
    
    # Minimum score (out of 50) to allow a rep to count.
    # Very low so reps still count when the person is genuinely exercising
    # even if the model underestimates quality for that exercise type.
    REP_SCORE_GATE = 5.0

    def _detect_and_count_reps(self, score: float, landmarks: np.ndarray = None, exercise_name: str = "", motion_delta: float = 0.0, form_status: str = "INCORRECT") -> Dict[str, Any]:
        """
        Rep detection — MediaPipe angle-based state machine.

        CRITICAL: The state machine ALWAYS runs on every frame so it
        can continuously track the rest→peak→rest angle cycle.
        The only gate on the final rep-increment is:
          - Score >= REP_SCORE_GATE  (person is at least trying)

        NO idle guard here — the state machine won't produce false
        reps when idle because the joint angles don't change.
        """
        rep_incremented = False
        set_completed = False
        exercise_completed = False
        rep_score = None

        # Accumulate scores for per-rep average
        self.rep_scores_buffer.append(score)

        # ── ALWAYS run the MediaPipe angle-based state machine ──
        # The state machine must see EVERY frame to properly track the
        # rest→peak→rest cycle.  When idle, angles don't change so no
        # false reps will fire.  Any gating here breaks cycle tracking
        # for slow rehab exercises like forward flexion / torso rotation.
        if landmarks is not None and self.rep_counter is not None:
            try:
                rep_detected = self.rep_counter.process(landmarks, exercise_name)

                if rep_detected:
                    # ── SOFT SCORE GATE: block rep only if score is very low ──
                    if score < self.REP_SCORE_GATE:
                        print(f"      [REP] rep detected but score={score:.1f} < {self.REP_SCORE_GATE} — SKIPPED")
                    else:
                        self.current_rep_count += 1
                        rep_incremented = True
                        rep_score = round(float(np.mean(self.rep_scores_buffer)), 2) if self.rep_scores_buffer else round(score, 2)
                        self.rep_scores_buffer = []
                        print(f"   REP #{self.current_rep_count}/{self.target_reps} | Set {self.current_set_count}/{self.target_sets} | Score: {rep_score}")

                        if self.current_rep_count >= self.target_reps:
                            set_completed = True
                            self.current_set_count += 1
                            self.current_rep_count = 0
                            print(f"   SET COMPLETE -> Set {self.current_set_count}")
                            if self.current_set_count > self.target_sets:
                                exercise_completed = True
                                self.current_set_count = self.target_sets
            except Exception as e:
                print(f"   Rep counter error: {e}")

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
    
    
    def process_frame_dataurl_keraal(self, frame_b64: str, language: str = "English", exercise_hint: str = "") -> Dict[str, Any]:
        """
        Process single frame through KERAAL pipeline.
        
        Pipeline:
        1. Extract BlazePose 33 landmarks
        2. Normalize (hip center + torso scaling)
        3. Add to rolling buffer (48 frames)
        4. When buffer full: predict exercise + correctness
        5. Compute raw score and form status
        6. Count reps at window level
        
        Args:
            frame_b64: Base64 encoded frame
            language: Language for feedback
            exercise_hint: User-selected exercise name (used for feedback when ML detection is uncertain)
        
        Returns:
            Response dict with frame_score, form_status, exercise_name, etc.
        """
        print("\n================ KERAAL FRAME PROCESSING ================")
        
        self.language = language
        self.frame_count += 1
        
        # 1️⃣ Extract MediaPipe landmarks
        print("➡️ Step 1: MediaPipe extraction (BlazePose 33)")
        frame, landmarks = self._extract_mediapipe_landmarks_keraal(frame_b64)
        
        if landmarks is None:
            print("❌ No pose detected")
            return {
                "frame_score": 0.0,
                "form_status": "NO_POSE",
                "llm_feedback": ["No person detected"],
                "exercise_name": "idle",
                "exercise_confidence": 0.0,
                "pipeline": "keraal",
                "rep_info": {
                    "rep_now": self.current_rep_count,
                    "rep_target": self.target_reps,
                    "set_now": self.current_set_count,
                    "set_target": self.target_sets,
                    "rep_incremented": False,
                },
                "landmarks": [],
            }
        
        # 2️⃣ Normalize landmarks (separate normalization for each model)
        print("➡️ Step 2: Normalize landmarks (dual normalization)")
        scoring_normalized = normalize_landmarks_scoring(landmarks)           # (99,) for scoring model
        exercise_normalized = normalize_landmarks_exercise_detection(landmarks)  # (33,3) for exercise model

        if self.pose_buffer.prev_frame is None:
            frame_motion_delta = 0.0
        else:
            frame_motion_delta = float(np.mean(np.abs(scoring_normalized - self.pose_buffer.prev_frame)))

        now_frame = time.time()
        if self.last_frame_time > 0.0:
            dt = max(1e-3, now_frame - self.last_frame_time)
            inst_fps = float(np.clip(1.0 / dt, 2.0, 30.0))
            self.frame_fps_ema = (self.fps_alpha * inst_fps) + ((1.0 - self.fps_alpha) * self.frame_fps_ema)
        self.last_frame_time = now_frame

        self.last_frame_motion = frame_motion_delta

        # Learn camera-specific jitter floor during low-motion segments
        if frame_motion_delta < (self.min_motion_for_rep * 1.2):
            self.motion_floor_ema = (0.1 * frame_motion_delta) + (0.9 * self.motion_floor_ema)

        self.dynamic_idle_motion_threshold = max(self.idle_motion_threshold, self.motion_floor_ema * 1.35)
        self.dynamic_min_motion_for_rep = max(self.min_motion_for_rep, self.motion_floor_ema * 1.8)
        self.min_idle_frames = max(10, int(self.min_idle_seconds * self.frame_fps_ema))

        self.motion_ema = (self.motion_alpha * frame_motion_delta) + ((1.0 - self.motion_alpha) * self.motion_ema)
        print(f"   Frame motion delta: {frame_motion_delta:.6f} | motion_ema: {self.motion_ema:.6f} | fps≈{self.frame_fps_ema:.1f} | idle_th={self.dynamic_idle_motion_threshold:.6f} | rep_th={self.dynamic_min_motion_for_rep:.6f}")
        
        # 3️⃣ Add to buffer (both normalizations)
        print("➡️ Step 3: Add to rolling buffer")
        self.pose_buffer.add(scoring_normalized, exercise_normalized)
        buffer_len = len(self.pose_buffer.positions)
        print(f"   Buffer: {buffer_len}/{WINDOW_SIZE} frames")
        
        # 4️⃣ If buffer not full, return warmup response
        if not self.pose_buffer.is_full():
            print("   ⏳ Buffer warming up...")
            return {
                "frame_score": 0.0,
                "form_status": "WARMUP",
                "llm_feedback": [],
                "exercise_name": "idle",
                "exercise_confidence": 0.0,
                "pipeline": "keraal",
                "rep_info": {
                    "rep_now": self.current_rep_count,
                    "rep_target": self.target_reps,
                    "set_now": self.current_set_count,
                    "set_target": self.target_sets,
                    "rep_incremented": False,
                },
                "landmarks": landmarks.tolist() if landmarks is not None else [],
            }
        
        # 5️⃣ Buffer is full - get sequence
        print("➡️ Step 4: Window-level predictions (buffer full)")
        sequence = self.pose_buffer.get_sequence()  # (1, 48, 198)
        
        # 6️⃣ Exercise detection (use exercise-specific normalized buffer)
        print("➡️ Step 5: Exercise detection")
        exercise_seq = self.pose_buffer.get_exercise_sequence()  # (1, 48, 33, 3)
        exercise_name, exercise_confidence = self._predict_exercise_detection(exercise_seq)
        exercise_display = KERAAL_EXERCISE_MAP.get(exercise_name, exercise_name)
        
        # ⭐ USE EXERCISE HINT: If user selected an exercise, prefer it for feedback
        # The ML model result is still shown as detected, but the HINT drives
        # RAG queries, LLM feedback, and rep counting for accuracy.
        feedback_exercise_name = exercise_display  # default: ML-detected display name
        if exercise_hint:
            # Normalize hint to a display name
            hint_lower = exercise_hint.lower().replace('_', ' ').strip()
            HINT_MAP = {
                'forward flexion': 'Forward Flexion', 'forward_flexion': 'Forward Flexion', 'ctk': 'Forward Flexion',
                'flank stretch': 'Flank Stretch', 'flank_stretch': 'Flank Stretch', 'elk': 'Flank Stretch',
                'torso rotation': 'Torso Rotation', 'torso_rotation': 'Torso Rotation', 'rtk': 'Torso Rotation',
                'pelvis rotation': 'Torso Rotation', 'pelvis_rotation': 'Torso Rotation',
            }
            resolved_hint = HINT_MAP.get(hint_lower, exercise_hint)
            # Use hint as the feedback exercise when ML confidence is low or doesn't match
            if exercise_confidence < 0.7 or resolved_hint != exercise_display:
                feedback_exercise_name = resolved_hint
                print(f"   ⭐ Using exercise_hint '{resolved_hint}' instead of ML-detected '{exercise_display}' (conf={exercise_confidence:.2f})")
        
        # ⭐ IDLE DETECTION: only when BOTH confidence is low AND motion is low.
        # Using AND prevents false IDLE during slow rehab exercises (forward
        # flexion, torso rotation) where motion_ema can dip below the threshold
        # while the person is genuinely exercising.
        if exercise_confidence < 0.4 and self.motion_ema < self.dynamic_idle_motion_threshold:
            self.idle_frames += 1
            if self.idle_frames >= self.min_idle_frames:
                print(f"   ⏸️  IDLE DETECTED (conf={exercise_confidence:.2f}, motion_ema={self.motion_ema:.6f})")
                return {
                    "frame_score": 0.0,
                    "form_status": "IDLE",
                    "llm_feedback": ["Please start the exercise"],
                    "exercise_name": "idle",
                    "exercise_confidence": exercise_confidence,
                    "pipeline": "keraal",
                    "rep_info": {
                        "rep_now": self.current_rep_count,
                        "rep_target": self.target_reps,
                        "set_now": self.current_set_count,
                        "set_target": self.target_sets,
                        "rep_incremented": False,
                    },
                    "landmarks": landmarks.tolist() if landmarks is not None else [],
                }
        else:
            self.idle_frames = 0  # Reset when movement detected
        
        # 7️⃣ Correctness prediction
        print("➡️ Step 6: Correctness prediction")
        correctness_score = self._predict_correctness(sequence)
        print(f"   Correctness: {correctness_score:.3f}")
        
        # 8️⃣ Compute raw score (correctness * 50)
        raw_score = correctness_score * SCORE_MULTIPLIER
        print(f"   Raw score: {raw_score:.2f}/50")
        
        # 9️⃣ Form status
        form_status = self._determine_form_status(correctness_score)
        print(f"   Form status: {form_status}")
        
        # 🔟 Rep detection at window level
        print("➡️ Step 7: Window-level rep detection")
        # Use RAW MediaPipe landmarks (0-1 range) for angle-based rep counter
        # NOT the normalized (hip-centered, torso-scaled) ones from the scoring buffer
        rep_info = self._detect_and_count_reps(raw_score, landmarks, feedback_exercise_name, motion_delta=frame_motion_delta, form_status=form_status)
        
        # 1️⃣1️⃣ Store score for aggregation
        self.score_history.append(raw_score)
        aggregated_score = self._get_aggregated_score()
        print(f"   Aggregated score (10s window): {aggregated_score:.2f}/50")
        
        # 1️⃣2️⃣ Generate LLM feedback based on aggregated score
        # Use the feedback_exercise_name (from hint or ML) for accurate RAG + LLM queries
        llm_feedback = self._generate_llm_feedback(form_status, aggregated_score, feedback_exercise_name, landmarks)
        
        # Store window prediction
        self.window_predictions.append({
            "exercise": exercise_name,
            "correctness": correctness_score,
            "frame_count": self.frame_count,
            "aggregated_score": aggregated_score
        })
        
        print("➡️ Returning response")
        
        return {
            "frame_score": round(raw_score, 2),
            "form_status": form_status,
            "llm_feedback": llm_feedback,
            # Return the feedback_exercise_name (hint-resolved) for correct UI display
            "exercise_name": feedback_exercise_name,
            "exercise_confidence": round(exercise_confidence, 3),
            "ml_detected_exercise": exercise_display,  # What ML actually detected
            "pipeline": "keraal",
            "correctness": round(correctness_score, 3),
            "aggregated_score": round(aggregated_score, 2),
            "rep_info": rep_info,
            # Return RAW MediaPipe landmarks (0-1 range) for skeleton visualization,
            # NOT the normalized (hip-centered) ones used by the model
            "landmarks": landmarks.tolist() if landmarks is not None else [],
        }
    
    
    def reset(self, *args, **kwargs):
        """Reset session state"""
        print("🔄 Resetting KERAAL session")
        
        self.pose_buffer.reset()
        self.current_rep_count = 0
        self.current_set_count = 1
        self.rep_scores_buffer = []
        self.frame_count = 0
        self.window_predictions.clear()
        self.score_history.clear()
        self.llm_feedback_cooldown = 0
        self.idle_frames = 0
        self.motion_ema = 0.0
        self.last_frame_motion = 0.0
        self.motion_floor_ema = self.idle_motion_threshold
        self.dynamic_idle_motion_threshold = self.idle_motion_threshold
        self.frame_fps_ema = 5.0
        self.last_frame_time = 0.0
        
        if self.rep_counter:
            with contextlib.suppress(Exception):
                self.rep_counter.reset()
        
        print("✅ KERAAL Session reset complete")
