# openpose_http_server.py

from flask import Flask, request, jsonify
import numpy as np
import cv2
import base64
import torch
import openpifpaf

app = Flask(__name__)

# Load OpenPifPaf model once
model, processor = openpifpaf.network.factory(checkpoint='resnet50')
model = model.to('cpu')
model.eval()

def dataurl_to_bgr(data_url):
    b64 = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def extract_keypoints(bgr):
    image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    pil_image = openpifpaf.datasets.pil_loader.image_to_pil(image)

    with torch.no_grad():
        pred, _, _ = processor.batch(model, [pil_image])

    if not pred or not pred[0]:
        return None

    # take first detected person
    keypoints = pred[0][0].data[:, :3]  # (17,3) x,y,conf
    return keypoints

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/pose", methods=["POST"])
def pose():
    payload = request.get_json()
    frame_b64 = payload.get("frame_b64")

    bgr = dataurl_to_bgr(frame_b64)
    if bgr is None:
        return jsonify({"ok": False, "error": "decode failed"}), 400

    kps = extract_keypoints(bgr)
    if kps is None:
        return jsonify({"ok": False, "error": "no_person"}), 200

    return jsonify({
        "ok": True,
        "keypoints": kps.tolist()
    })
    
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=9001, threaded=True)