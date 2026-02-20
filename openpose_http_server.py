# openpose_http_server.py

from flask import Flask, request, jsonify
import numpy as np
import cv2
import base64
import mediapipe as mp

app = Flask(__name__)

mp_pose = mp.solutions.pose
pose_model = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# BODY_25 layout mapping
# Index reference matches OpenPose BODY_25 ordering

def dataurl_to_bgr(data_url):
    try:
        b64 = data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None

def extract_keypoints(bgr):
    image_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    results = pose_model.process(image_rgb)

    if not results.pose_landmarks:
        return None

    h, w, _ = bgr.shape
    body25 = np.zeros((25, 3), dtype=np.float32)

    lm = results.pose_landmarks.landmark

    # Direct anatomical mapping
    body25[0]  = [lm[0].x*w,  lm[0].y*h,  lm[0].visibility]   # Nose
    body25[5]  = [lm[11].x*w, lm[11].y*h, lm[11].visibility]  # L Shoulder
    body25[2]  = [lm[12].x*w, lm[12].y*h, lm[12].visibility]  # R Shoulder
    body25[6]  = [lm[13].x*w, lm[13].y*h, lm[13].visibility]  # L Elbow
    body25[3]  = [lm[14].x*w, lm[14].y*h, lm[14].visibility]  # R Elbow
    body25[7]  = [lm[15].x*w, lm[15].y*h, lm[15].visibility]  # L Wrist
    body25[4]  = [lm[16].x*w, lm[16].y*h, lm[16].visibility]  # R Wrist
    body25[12] = [lm[23].x*w, lm[23].y*h, lm[23].visibility]  # L Hip
    body25[9]  = [lm[24].x*w, lm[24].y*h, lm[24].visibility]  # R Hip
    body25[13] = [lm[25].x*w, lm[25].y*h, lm[25].visibility]  # L Knee
    body25[10] = [lm[26].x*w, lm[26].y*h, lm[26].visibility]  # R Knee
    body25[14] = [lm[27].x*w, lm[27].y*h, lm[27].visibility]  # L Ankle
    body25[11] = [lm[28].x*w, lm[28].y*h, lm[28].visibility]  # R Ankle

    # Compute MidHip (index 8)
    body25[8] = (body25[12] + body25[9]) / 2.0

    # Compute Neck (index 1)
    body25[1] = (body25[5] + body25[2]) / 2.0

    return body25

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/pose", methods=["POST"])
def pose():
    payload = request.get_json()
    frame_b64 = payload.get("frame_b64")

    bgr = dataurl_to_bgr(frame_b64)
    if bgr is None:
        return jsonify({"ok": False, "error": "decode_failed"}), 400

    keypoints = extract_keypoints(bgr)
    if keypoints is None:
        return jsonify({"ok": False, "error": "no_person"}), 200

    return jsonify({
        "ok": True,
        "keypoints": keypoints.tolist()
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9001, threaded=True)