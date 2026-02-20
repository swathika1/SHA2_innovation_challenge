import numpy as np
import tensorflow as tf
import joblib
import cv2
from collections import Counter
from Rehab_Scorer_Coach.src.config import AppConfig

# =========================================================
# CONFIG
# =========================================================

SEQ_LEN = 100
CONF_THRESHOLD = 0.6
SMOOTHING_WINDOW = 8

fgbg = cv2.createBackgroundSubtractorMOG2(
    history=200,
    varThreshold=50,
    detectShadows=False
)
# =========================================================
# LOAD MODELS
# =========================================================

# RGB exercise classifier
exercise_model = tf.keras.models.load_model(
    AppConfig.exercise_detection_model_path
)

# Pose-based scoring model
scoring_model = tf.keras.models.load_model(
    AppConfig.scoring_model_path
)

# Only scoring uses scaler
scoring_scaler = joblib.load(AppConfig.scoring_scaler_path)

# =========================================================
# CLASS ORDER (MUST MATCH TRAINING)
# =========================================================

CLASS_NAMES = [
    "ideal",
    "lateral_trunk_tilt",
    "lifting_of_arms",
    "pelvis_rotation",
    "squat",
    "trunk_rotation"
]

# =========================================================
# POSE FEATURE PROCESSING (FOR SCORE MODEL)
# =========================================================

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

# =========================================================
# EXERCISE PREDICTION (RGB FRAME-BASED)
# =========================================================

PRED_BUFFER = []
def resize_with_padding(img, target_size=128):
    # sourcery skip: inline-immediately-returned-variable
    h, w = img.shape[:2]
    scale = target_size / max(h, w)

    new_h = int(h * scale)
    new_w = int(w * scale)

    resized = cv2.resize(img, (new_w, new_h))

    pad_h = target_size - new_h
    pad_w = target_size - new_w

    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    padded = cv2.copyMakeBorder(
        resized,
        top, bottom, left, right,
        borderType=cv2.BORDER_CONSTANT,
        value=[0, 0, 0]
    )

    return padded

def predict_exercise_v1(frame: np.ndarray):
    global PRED_BUFFER

    # Apply background subtraction
    fg_mask = fgbg.apply(frame)

    # Clean mask
    kernel = np.ones((5, 5), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_DILATE, kernel)

    contours, _ = cv2.findContours(
        fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if len(contours) == 0:
        return "idle", 0.0

    # Largest moving object
    largest = max(contours, key=cv2.contourArea)

    if cv2.contourArea(largest) < 2000:
        return "idle", 0.0

    x, y, w, h = cv2.boundingRect(largest)

    pad = 30
    x = max(0, x - pad)
    y = max(0, y - pad)
    w = min(frame.shape[1] - x, w + 2 * pad)
    h = min(frame.shape[0] - y, h + 2 * pad)

    crop = frame[y:y+h, x:x+w]

    # BGR → RGB
    crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)

    # Preserve aspect ratio
    img = resize_with_padding(crop, 128)

    img = img.astype("float32") / 255.0
    img = np.expand_dims(img, axis=0)

    probs = exercise_model.predict(img, verbose=0)[0]
    class_idx = int(np.argmax(probs))
    confidence = float(probs[class_idx])

    if confidence < CONF_THRESHOLD:
        return "idle", confidence

    PRED_BUFFER.append(class_idx)
    if len(PRED_BUFFER) > SMOOTHING_WINDOW:
        PRED_BUFFER.pop(0)

    most_common = Counter(PRED_BUFFER).most_common(1)[0][0]
    exercise_name = CLASS_NAMES[most_common]

    return exercise_name, confidence

def predict_exercise(frame: np.ndarray):
    global PRED_BUFFER

    # Convert BGR (OpenCV) → RGB (VERY IMPORTANT)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Resize EXACT same as training
    img = cv2.resize(frame, (128, 128))

    # Convert to float32
    img = img.astype("float32")

    # SAME normalization as training
    #img = img / 255.0

    # Add batch dimension
    img = np.expand_dims(img, axis=0)

    probs = exercise_model.predict(img, verbose=0)[0]
    class_idx = int(np.argmax(probs))
    confidence = float(probs[class_idx])

    print("Probs:", probs)

    if confidence < CONF_THRESHOLD:
        return "unknown", confidence

    #PRED_BUFFER.append(class_idx)
    #if len(PRED_BUFFER) > SMOOTHING_WINDOW:
    #   PRED_BUFFER.pop(0)

    #most_common = Counter(PRED_BUFFER).most_common(1)[0][0]
    #exercise_name = CLASS_NAMES[most_commo n]
    exercise_name = CLASS_NAMES[class_idx]
    print(exercise_name)
    print("Image sum:", np.sum(img))
    print("Image mean:", np.mean(img))
    
    print("Input shape:", img.shape)
    print("Sum:", np.sum(img))
    print("First pixel:", img[0,0,0])
    return exercise_name, confidence

def predict_exercise_old(frame: np.ndarray):
    """
    Takes raw OpenCV BGR frame.
    Returns (exercise_name, confidence)
    """

    global PRED_BUFFER

    img = cv2.resize(frame, (160, 160))
    img = img.astype("float32") / 255.0
    img = np.expand_dims(img, axis=0)

    probs = exercise_model.predict(img, verbose=0)[0]
    class_idx = int(np.argmax(probs))
    confidence = float(probs[class_idx])

    # Confidence gate
    if confidence < CONF_THRESHOLD:
        return "unknown", confidence

    # Smoothing
    PRED_BUFFER.append(class_idx)
    if len(PRED_BUFFER) > SMOOTHING_WINDOW:
        PRED_BUFFER.pop(0)

    most_common = Counter(PRED_BUFFER).most_common(1)[0][0]
    exercise_name = CLASS_NAMES[most_common]

    return exercise_name, confidence

# =========================================================
# SCORE PREDICTION (POSE SEQUENCE)
# =========================================================

SEQUENCE_BUFFER = []

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
    PRED_BUFFER.clear()