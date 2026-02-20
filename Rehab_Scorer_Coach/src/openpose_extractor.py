# Rehab_Scorer_Coach/src/openpose_extractor.py

import numpy as np
import cv2
import openpifpaf


class OpenPoseExtractor:
    """
    Real OpenPose-style pose extraction using OpenPifPaf.
    Outputs 25-keypoint style features mapped to Kimore 100-dim space.
    """

    def __init__(self):
        self.predictor = openpifpaf.Predictor(checkpoint="resnet50")

    def detect_keypoints(self, bgr_image):
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)

        predictions, _, _ = self.predictor.numpy_image(rgb)

        if not predictions:
            return None

        # Take most confident person
        ann = max(predictions, key=lambda x: x.score)
        keypoints = ann.data  # shape (17, 3) COCO format

        return keypoints  # (17,3) → x,y,confidence

    def coco_to_openpose25(self, kp17):
        """
        Map COCO 17 keypoints to OpenPose 25-style layout.
        """
        if kp17 is None:
            return None

        op25 = np.zeros((25, 3), dtype=np.float32)

        # COCO index mapping
        mapping = {
            0: 0,   # nose
            5: 5,   # left shoulder
            6: 2,   # right shoulder
            7: 6,   # left elbow
            8: 3,   # right elbow
            9: 7,   # left wrist
            10: 4,  # right wrist
            11: 12, # left hip
            12: 9,  # right hip
            13: 13, # left knee
            14: 10, # right knee
            15: 14, # left ankle
            16: 11, # right ankle
        }

        for coco_idx, op_idx in mapping.items():
            op25[op_idx] = kp17[coco_idx]

        return op25

    def to_feature100(self, op25):
        """
        Convert 25x3 → Kimore-style 100D feature.
        """
        if op25 is None:
            return None

        xy = op25[:, :2]

        # Center at mid-hip
        left_hip = xy[12]
        right_hip = xy[9]
        center = (left_hip + right_hip) / 2.0
        xy = xy - center

        # Scale by torso length
        left_shoulder = xy[5]
        scale = np.linalg.norm(left_shoulder)
        if scale > 1e-6:
            xy = xy / scale

        feat = xy.flatten()  # 25*2 = 50

        # Duplicate with velocity placeholder (temporal compatibility)
        feat = np.concatenate([feat, feat])  # 100 dims

        return feat.astype(np.float32)