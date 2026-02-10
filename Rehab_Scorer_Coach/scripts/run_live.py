from src.llm_vision import get_correction_advice_from_vision_llm
import argparse
import time
from collections import deque

import cv2
import numpy as np

from src.config import AppConfig
from src.pose_extractor import PoseExtractor
from src.feature_builder import landmarks_to_feature100, resample_to_T
from src.model_infer import ScoreModel
from src.session_scoring import SessionScorer
from src.llm_vision import get_correction_advice_from_vision_llm
from src.tts import TTS

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration_sec", type=int, default=60)
    parser.add_argument("--exercise_name", type=str, default="rehab exercise")
    parser.add_argument("--camera_index", type=int, default=0)

    # optional overrides
    parser.add_argument("--threshold_low", type=float, default=None)
    parser.add_argument("--threshold_high", type=float, default=None)
    parser.add_argument("--cooldown_sec", type=float, default=None)
    parser.add_argument("--smoothing_window", type=int, default=None)

    args = parser.parse_args()
    cfg = AppConfig()

    if args.threshold_low is not None: cfg.threshold_low = args.threshold_low
    if args.threshold_high is not None: cfg.threshold_high = args.threshold_high
    if args.cooldown_sec is not None: cfg.cooldown_seconds = args.cooldown_sec
    if args.smoothing_window is not None: cfg.smoothing_window = args.smoothing_window

    # Load components
    pose = PoseExtractor(str(cfg.pose_model_path))
    scorer = ScoreModel(
        keras_path=str(cfg.keras_model_path),
        x_scaler_path=str(cfg.x_scaler_path),
        y_map_path=str(cfg.y_map_path),
    )
    tts = TTS(rate=180)
    session = SessionScorer(smoothing_window=cfg.smoothing_window)

    # Rolling buffer of sampled feature vectors
    feat_buffer = deque(maxlen=60)  # 60 samples @2s each -> 120 seconds window

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")

    print("Running live. Press 'q' to quit.")
    start_time = time.time()
    last_sample_time = 0.0

    # Hysteresis + cooldown
    in_alert_state = False
    last_spoken_time = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        now = time.time()
        elapsed = now - start_time
        if elapsed > args.duration_sec:
            break

        # Sample every 2 seconds
        if (now - last_sample_time) >= cfg.sample_every_seconds:
            last_sample_time = now

            landmarks = pose.detect_landmarks(frame)
            if landmarks is not None:
                feat100 = landmarks_to_feature100(landmarks)  # (100,)
                feat_buffer.append((now, frame.copy(), feat100))
                print(f"[t={elapsed:.1f}s] Pose OK. Buffer size={len(feat_buffer)}")
            else:
                print(f"[t={elapsed:.1f}s] No pose detected.")

            # Predict if we have at least a few samples
            if len(feat_buffer) >= 5:
                feats = np.stack([x[2] for x in feat_buffer], axis=0)  # (n,100)
                seq = resample_to_T(feats, cfg.target_timesteps)       # (100,100)
                X_seq_1 = seq[None, :, :]                              # (1,100,100)

                score = scorer.predict_score_0_50(X_seq_1)
                session.add_clip_score(score)
                smooth = session.smoothed_score()

                print(f"  -> Score: {score:.2f} | Smoothed({cfg.smoothing_window}): {smooth:.2f}")

                # Hysteresis logic
                if not in_alert_state and smooth < cfg.threshold_low:
                    in_alert_state = True
                elif in_alert_state and smooth > cfg.threshold_high:
                    in_alert_state = False

                # Cooldown: speak only occasionally
                if in_alert_state and (now - last_spoken_time) >= cfg.cooldown_seconds:
                    bad_frame = feat_buffer[-1][1]
                    advice = get_correction_advice_from_vision_llm(
                        bad_frame,
                        exercise_name=args.exercise_name
                    )
                    print("  -> Advice:", advice)
                    tts.speak(advice)
                    last_spoken_time = now

        # Display overlay
        display = frame.copy()
        cv2.putText(display, f"Elapsed: {elapsed:.1f}s", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.putText(display, f"Clips: {len(session.clip_scores)}", (10, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        cv2.putText(display, f"Smooth: {session.smoothed_score():.2f}", (10, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        state = "ALERT" if in_alert_state else "OK"
        cv2.putText(display, f"State: {state}", (10, 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

        cv2.imshow("Rehab Score Coach", display)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    out = session.to_json()
    print("\n=== Session Result ===")
    print(out)  # {"Overall Session Score": X.XX}


if __name__ == "__main__":
    main()