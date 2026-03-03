"""
MediaPipe Rule-Based Rep Counter for Rehabilitation Exercises
Provides accurate, stable rep detection for both KERAAL and KIMORE pipelines
"""

import numpy as np
from typing import Dict, Tuple, Optional
import math


class RepCounterMediaPipe:
    """
    Rule-based rep counter using MediaPipe pose landmarks (33 points)
    Detects reps by monitoring joint angles and positions
    """
    
    def __init__(self):
        self.state = "rest"  # States: rest, moving_up, moving_down
        self.rep_count = 0
        self.prev_landmarks = None
        self.movement_threshold = 15  # degrees
        self.smoothing_factor = 0.7
        
    def _calculate_angle(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        """
        Calculate angle at p2 formed by p1, p2, p3
        Returns angle in degrees (0-180)
        """
        try:
            # Vector from p2 to p1
            v1 = p1[:2] - p2[:2]
            # Vector from p2 to p3
            v2 = p3[:2] - p2[:2]
            
            # Calculate angle using dot product
            dot_product = np.dot(v1, v2)
            magnitude_v1 = np.linalg.norm(v1)
            magnitude_v2 = np.linalg.norm(v2)
            
            if magnitude_v1 == 0 or magnitude_v2 == 0:
                return 0
            
            cos_angle = dot_product / (magnitude_v1 * magnitude_v2)
            cos_angle = np.clip(cos_angle, -1, 1)
            angle = np.arccos(cos_angle)
            return np.degrees(angle)
        except:
            return 0
    
    def _get_distance(self, p1: np.ndarray, p2: np.ndarray) -> float:
        """Calculate Euclidean distance between two points"""
        return np.linalg.norm(p1[:2] - p2[:2])
    
    def _get_vertical_distance(self, p1: np.ndarray, p2: np.ndarray) -> float:
        """Calculate vertical (y-axis) distance between two points"""
        return abs(p1[1] - p2[1])
    
    def detect_squat(self, landmarks: np.ndarray) -> bool:
        """
        Detect squat rep
        Key joints: hip (23/24), knee (25/26), ankle (27/28)
        Down: knee angle < 90°, Up: knee angle > 160°
        """
        try:
            # Left side landmarks
            left_hip = landmarks[23]
            left_knee = landmarks[25]
            left_ankle = landmarks[27]
            
            # Calculate knee angle
            knee_angle = self._calculate_angle(left_hip, left_knee, left_ankle)
            
            # Detect state change
            prev_state = self.state
            
            if knee_angle < 90:  # Squat down position
                self.state = "moving_down"
            elif knee_angle > 160 and self.state == "moving_down":  # Standing back up
                self.state = "moving_up"
                return True  # Rep complete
            elif knee_angle > 150:
                self.state = "rest"
            
            return False
        except:
            return False
    
    def detect_lifting_of_arms(self, landmarks: np.ndarray) -> bool:
        """
        Detect arm lifting (shoulder raise)
        Key joints: shoulder (11/12), elbow (13/14), wrist (15/16)
        Down: shoulder-wrist distance low, Up: shoulder-wrist distance high
        """
        try:
            # Use both shoulders and average
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_wrist = landmarks[15]
            right_wrist = landmarks[16]
            
            # Calculate vertical distance (height)
            left_height = self._get_vertical_distance(left_shoulder, left_wrist)
            right_height = self._get_vertical_distance(right_shoulder, right_wrist)
            avg_height = (left_height + right_height) / 2
            
            # Threshold for arm raise
            up_threshold = 0.3  # 30% of body height
            down_threshold = 0.1  # 10% of body height
            
            if avg_height < down_threshold:
                self.state = "rest"
            elif avg_height > up_threshold and self.state != "moving_up":
                self.state = "moving_up"
                if self.prev_state == "rest" or self.prev_state == "moving_down":
                    self.rep_count += 1
                    return True
            elif avg_height < down_threshold and self.state == "moving_up":
                self.state = "moving_down"
            
            return False
        except:
            return False
    
    def detect_lateral_trunk_tilt(self, landmarks: np.ndarray) -> bool:
        """
        Detect lateral trunk tilt (side bend)
        Key: hip-shoulder distance changes side to side
        """
        try:
            # Pelvis and shoulders
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            
            # Calculate distances
            left_side_dist = self._get_distance(left_hip, left_shoulder)
            right_side_dist = self._get_distance(right_hip, right_shoulder)
            
            # Side bend detected when one side is significantly compressed
            compression_ratio = min(left_side_dist, right_side_dist) / max(left_side_dist, right_side_dist)
            
            if compression_ratio < 0.85:  # One side compressed
                self.state = "moving_down"
            elif compression_ratio > 0.95 and self.state == "moving_down":
                self.state = "moving_up"
                return True  # Rep complete
            
            return False
        except:
            return False
    
    def detect_trunk_rotation(self, landmarks: np.ndarray) -> bool:
        """
        Detect trunk rotation
        Key: shoulder angle changes relative to hips
        """
        try:
            # Shoulders and hips
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            
            # Calculate angles
            shoulder_angle = self._calculate_angle(left_shoulder, right_shoulder, landmarks[0])
            hip_angle = self._calculate_angle(left_hip, right_hip, landmarks[0])
            
            # Angle difference indicates rotation
            angle_diff = abs(shoulder_angle - hip_angle)
            
            if angle_diff > 30:  # Significant rotation
                self.state = "moving_down"
            elif angle_diff < 10 and self.state == "moving_down":
                self.state = "moving_up"
                return True
            
            return False
        except:
            return False
    
    def detect_forward_flexion(self, landmarks: np.ndarray) -> bool:
        """
        Detect forward flexion (touching toes)
        Key: hip to hand distance decreases
        """
        try:
            # Hips and hands
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_hand = landmarks[19]
            right_hand = landmarks[20]
            
            hip_center = (left_hip + right_hip) / 2
            hand_avg = (left_hand + right_hand) / 2
            
            # Vertical distance
            flex_distance = self._get_vertical_distance(hip_center, hand_avg)
            
            if flex_distance > 0.4:  # Standing position
                self.state = "rest"
            elif flex_distance < 0.2 and self.state == "rest":
                self.state = "moving_down"
                self.rep_count += 1
                return True
            elif flex_distance > 0.3 and self.state == "moving_down":
                self.state = "moving_up"
            
            return False
        except:
            return False
    
    def detect_flank_stretch(self, landmarks: np.ndarray) -> bool:
        """
        Detect flank stretch (side stretch with overhead arm)
        Key: torso and arm position changes
        """
        try:
            # Torso and elevated arm
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            
            # Calculate lateral flex
            left_side = self._get_distance(left_shoulder, left_hip)
            right_side = self._get_distance(right_shoulder, right_hip)
            
            # Stretch detected when sides are unequal
            if left_side > right_side * 1.15:  # Left stretch
                self.state = "moving_down"
            elif right_side > left_side * 1.15:  # Right stretch
                self.state = "moving_down"
            elif abs(left_side - right_side) < 0.05 and self.state == "moving_down":
                self.state = "moving_up"
                return True
            
            return False
        except:
            return False
    
    def detect_torso_rotation(self, landmarks: np.ndarray) -> bool:
        """
        Detect torso rotation
        Key: shoulder position relative to hips
        """
        try:
            # Upper and lower body
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            
            # Shoulder angle
            shoulder_x = (left_shoulder[0] + right_shoulder[0]) / 2
            hip_x = (left_hip[0] + right_hip[0]) / 2
            
            # Rotation detected by x offset
            rotation_offset = abs(shoulder_x - hip_x)
            
            if rotation_offset > 0.1:
                self.state = "moving_down"
            elif rotation_offset < 0.05 and self.state == "moving_down":
                self.state = "moving_up"
                return True
            
            return False
        except:
            return False
    
    def detect_pelvis_rotation(self, landmarks: np.ndarray) -> bool:
        """
        Detect pelvis rotation
        Key: hip angle changes
        """
        try:
            # Hips and knees
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            left_knee = landmarks[25]
            right_knee = landmarks[26]
            
            # Calculate hip angle
            hip_angle = self._calculate_angle(left_hip, right_hip, (left_knee + right_knee) / 2)
            
            if hip_angle > 160:
                self.state = "rest"
            elif hip_angle < 140 and self.state == "rest":
                self.state = "moving_down"
                self.rep_count += 1
                return True
            elif hip_angle > 160 and self.state == "moving_down":
                self.state = "moving_up"
            
            return False
        except:
            return False
    
    def count_rep(self, landmarks: np.ndarray, exercise_name: str) -> bool:
        """
        Main method to detect a rep for given exercise
        Returns True if a rep was completed
        """
        if landmarks is None or len(landmarks) < 33:
            return False
        
        # Normalize landmarks if needed
        if landmarks.max() > 1.5:  # Likely in pixel coordinates
            landmarks = landmarks.copy()
            landmarks[:, :2] /= 720  # Normalize to 0-1 range
        
        # Call appropriate detector
        rep_detected = False
        exercise_name = exercise_name.lower().strip()
        
        if "squat" in exercise_name:
            rep_detected = self.detect_squat(landmarks)
        elif "lifting" in exercise_name or "arm" in exercise_name:
            rep_detected = self.detect_lifting_of_arms(landmarks)
        elif "lateral" in exercise_name or "tilt" in exercise_name:
            rep_detected = self.detect_lateral_trunk_tilt(landmarks)
        elif "trunk" in exercise_name and "rotation" in exercise_name:
            rep_detected = self.detect_trunk_rotation(landmarks)
        elif "forward" in exercise_name or "flexion" in exercise_name:
            rep_detected = self.detect_forward_flexion(landmarks)
        elif "flank" in exercise_name or "stretch" in exercise_name:
            rep_detected = self.detect_flank_stretch(landmarks)
        elif "pelvis" in exercise_name:
            rep_detected = self.detect_pelvis_rotation(landmarks)
        elif "torso" in exercise_name and "rotation" in exercise_name:
            rep_detected = self.detect_torso_rotation(landmarks)
        
        self.prev_landmarks = landmarks.copy()
        return rep_detected
    
    def reset(self):
        """Reset counter for new exercise"""
        self.state = "rest"
        self.rep_count = 0
        self.prev_landmarks = None
    
    def get_state(self) -> Dict:
        """Get current counter state"""
        return {
            "rep_count": self.rep_count,
            "state": self.state,
            "status": "detecting" if self.state != "rest" else "ready"
        }


# Factory function for easy initialization
def create_rep_counter() -> RepCounterMediaPipe:
    """Create a new rep counter instance"""
    return RepCounterMediaPipe()
