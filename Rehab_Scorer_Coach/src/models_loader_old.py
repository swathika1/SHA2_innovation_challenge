import numpy as np
import tensorflow as tf
import joblib
import json
from Rehab_Scorer_Coach.src.config import AppConfig

SEQ_LEN = 100

# Load trained models
exercise_model = tf.keras.models.load_model(AppConfig.exercise_detection_model_path)
scoring_model = tf.keras.models.load_model(AppConfig.scoring_model_path)

# Load scalers
exercise_scaler = joblib.load(AppConfig.exercise_scaler_path)
scoring_scaler = joblib.load(AppConfig.scoring_scaler_path)


# Produces exactly 25 × 2 = 50 features
SELECTED_LANDMARKS = [
    0,   # Nose
    11, 12,  # Shoulders
    13, 14,  # Elbows
    15, 16,  # Wrists
    23, 24,  # Hips
    25, 26,  # Knees
    27, 28,  # Ankles
    29, 30,  # Heels
    31, 32,  # Foot index
    7, 8,    # Ears
    9, 10,   # Mouth
    1, 2, 3, 4  # Eyes
]

def normalize_pose_xy_old(keypoints_xy: np.ndarray) -> np.ndarray:
    """
    Normalize pose coordinates by centering and scaling.
    """
    center = keypoints_xy.mean(axis=0)
    normalized = keypoints_xy - center
    scale = np.linalg.norm(normalized)
    if scale > 0:
        normalized /= scale
    return normalized

def normalize_pose_xy(keypoints_xy: np.ndarray) -> np.ndarray:
    # sourcery skip: inline-immediately-returned-variable
    """
    Match Kimore training normalization exactly:
    - Center at MidHip (index 8)
    - Scale by torso length (Neck index 1)
    """

    # keypoints_xy shape: (33,2) from MediaPipe
    # We need BODY_25 layout assumption

    # Select only 25 joints in correct order
    xy = keypoints_xy[SELECTED_LANDMARKS].reshape(25, 2)

    # MidHip index in BODY_25 = 8
    midhip = xy[8:9, :]
    xy = xy - midhip

    # Neck index = 1
    neck = xy[1, :]
    torso_len = np.linalg.norm(neck)

    if torso_len < 1e-6:
        torso_len = 1.0

    xy = xy / torso_len

    return xy

def to_50d(keypoints_xy: np.ndarray) -> np.ndarray:
    return keypoints_xy.reshape(50)

def to_50d_old(keypoints_xy: np.ndarray) -> np.ndarray:
    """
    Convert 33×2 MediaPipe pose → 50D vector (25 joints × 2)
    """
    selected = keypoints_xy[SELECTED_LANDMARKS]
    feature = selected.flatten()

    # Safety check
    if feature.shape[0] != 50:
        raise ValueError(f"Feature dimension mismatch: got {feature.shape[0]}, expected 50")

    return feature


# ---------------------------------------------------------
# Exercise Prediction (Frame-Level)
# ---------------------------------------------------------

def predict_exercise_old(feature_50d: np.ndarray):
    """
    Predict exercise label + confidence.
    """
    x = exercise_scaler.transform(feature_50d.reshape(1, -1))
    probs = exercise_model.predict(x, verbose=0)[0]

    class_idx = np.argmax(probs)
    confidence = float(probs[class_idx])

    # Replace with your actual class names
    CLASS_NAMES = ["squat", "lunge", "pushup", "unknown"]

    exercise_name = CLASS_NAMES[class_idx]

    return exercise_name, confidence

def predict_exercise(feature_50d: np.ndarray):
    x = exercise_scaler.transform(feature_50d.reshape(1, -1))
    probs = exercise_model.predict(x, verbose=0)[0]

    class_idx = int(np.argmax(probs))
    confidence = float(probs[class_idx])

    # Auto-generate fallback names if we don't know real labels
    num_classes = probs.shape[0]

    if class_idx >= num_classes:
        return "unknown", confidence

    #exercise_name = f"class_{class_idx}"
    CLASS_NAMES = [
        "squat",
        "lifting_of_arms",
        "lateral_trunk_tilt",
        "trunk_rotation",
        "pelvis_rotation"
    ]

    if class_idx < len(CLASS_NAMES):
        exercise_name = CLASS_NAMES[class_idx]
    else:
        exercise_name = "unknown"
        
    print("Predicted class:", class_idx)
    print("Confidence:", confidence)
    print("All probs:", probs)
    return exercise_name, confidence


# ---------------------------------------------------------
# Score Prediction (Sequence-Based)
# ---------------------------------------------------------

SEQUENCE_BUFFER = []

def predict_score(feature_50d: np.ndarray):
    """
    Collect 100 frames → run score model.
    Returns None until buffer full.
    """
    global SEQUENCE_BUFFER

    SEQUENCE_BUFFER.append(feature_50d)

    if len(SEQUENCE_BUFFER) < 100: #100
        return None

    sequence = np.array(SEQUENCE_BUFFER[-100:])  # last 100 frames
    #sequence = scoring_scaler.transform(sequence)

    sequence = sequence.reshape(1, 100, 50)

    score = scoring_model.predict(sequence, verbose=0)[0][0]
    #normalized_score = (float(score) / 300.0) * 50.0
    return float(score)


def reset_sequence():
    global SEQUENCE_BUFFER
    SEQUENCE_BUFFER = []