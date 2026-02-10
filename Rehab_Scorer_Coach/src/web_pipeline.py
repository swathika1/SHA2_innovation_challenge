import time
from collections import deque
import numpy as np
import cv2

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.pose_extractor import PoseExtractor
from Rehab_Scorer_Coach.src.feature_builder import landmarks_to_feature100, resample_to_T
from Rehab_Scorer_Coach.src.model_infer import ScoreModel

# Use your Gemini LLM implementation (already exists in your folder)
from Rehab_Scorer_Coach.src.llm_vision_gemini import get_correction_advice_from_vision_llm
from Rehab_Scorer_Coach.src.llm_pose_groq import get_correction_advice_from_pose


def dataurl_to_bgr(data_url: str):
    # sourcery skip: inline-immediately-returned-variable
    """
    data:image/jpeg;base64,... -> BGR image (numpy)
    """
    if "," not in data_url:
        return None
    b64 = data_url.split(",", 1)[1]
    import base64
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _text_to_bullets(text: str, max_items=4):
    # sourcery skip: use-named-expression
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = []
    for ln in lines:
        ln = ln.lstrip("•- ").strip()
        if ln:
            bullets.append(ln)
    if not bullets:
        # fallback: split by sentences
        bullets = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return bullets[:max_items]


class WebRehabPipeline:
    """
    Called by Flask endpoint:
        - accepts a browser frame (dataURL)
        - returns score + status + LLM feedback
    """
    def __init__(self):
        self.cfg = AppConfig()

        self.pose = PoseExtractor(str(self.cfg.pose_model_path))
        self.scorer = ScoreModel(
            keras_path=str(self.cfg.keras_model_path),
            x_scaler_path=str(self.cfg.x_scaler_path),
            y_map_path=str(self.cfg.y_map_path),
        )

        # Rolling buffer of recent features to form a sequence
        self.feat_buffer = deque(maxlen=30)  # if polling every ~2s => ~1 min context

        # default controls (can be overridden by /api/session/start)
        self.threshold = 30.0
        self.cooldown_seconds = 10.0
        self.last_llm_time = 0.0
        self.exercise_name = "exercise"

    def reset(self, threshold=30.0, exercise_name="exercise", cooldown_seconds=10.0):
        self.feat_buffer.clear()
        self.threshold = float(threshold)
        self.exercise_name = exercise_name
        self.cooldown_seconds = float(cooldown_seconds)
        self.last_llm_time = 0.0

    def process_frame_dataurl(self, frame_b64: str):
        bgr = dataurl_to_bgr(frame_b64)
        if bgr is None:
            return {
                "frame_score": 0.0,
                "form_status": "NO_FRAME",
                "llm_feedback": ["No frame received from browser."]
            }

        landmarks = self.pose.detect_landmarks(bgr)
        if landmarks is None:
            return {
                "frame_score": 0.0,
                "form_status": "NO_POSE",
                "llm_feedback": ["Please adjust camera so your body is visible and well-lit."]
            }

        feat100 = landmarks_to_feature100(landmarks)  # (100,)
        self.feat_buffer.append(feat100)

        # Need at least a few points
        if len(self.feat_buffer) < 3:
            return {
                "frame_score": 0.0,
                "form_status": "WARMUP",
                "llm_feedback": []
            }

        feats = np.stack(list(self.feat_buffer), axis=0)     # (n, 100)
        seq = resample_to_T(feats, self.cfg.target_timesteps)  # (100,100)
        X_seq_1 = seq[None, :, :]                            # (1,100,100)

        score = self.scorer.predict_score_0_50(X_seq_1)
        status = "CORRECT" if score >= self.threshold else "WRONG"

        r = """
        feedback_list = []
        now = time.time()
        if status == "WRONG" and (now - self.last_llm_time) >= self.cooldown_seconds:
            txt = get_correction_advice_from_vision_llm(bgr, exercise_name=self.exercise_name)
            feedback_list = _text_to_bullets(txt, max_items=4)
            self.last_llm_time = now
        """
            
        feedback_list = []
        now = time.time()

        if status == "WRONG" and (now - self.last_llm_time) >= self.cooldown_seconds:
            try:
                #txt = get_correction_advice_from_vision_llm(bgr, exercise_name=self.exercise_name)
                # Make a compact text summary from landmarks
                # Example: use a few key joints; adapt to your landmark format
                pose_summary = str(landmarks[:10])  # quick demo; better: angles like knee/hip/back

                txt = get_correction_advice_from_pose(pose_summary, exercise_name=self.exercise_name)

                feedback_list = _text_to_bullets(txt, max_items=4)
            except Exception as e:
                feedback_list = [f"LLM error: {type(e).__name__}: {e}"]

            self.last_llm_time = now
            self.last_feedback_list = feedback_list

        # If no new feedback this tick, keep last feedback so UI doesn’t look empty
        if not feedback_list:
            feedback_list = self.last_feedback_list

        return {
            "frame_score": round(float(score), 2),
            "form_status": status,
            "llm_feedback": feedback_list
        }