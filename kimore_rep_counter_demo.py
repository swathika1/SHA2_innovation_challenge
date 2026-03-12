#!/usr/bin/env python3
"""
Kimore Rep Counter — Standalone Webcam Demo

Counts reps in real-time for 5 Kimore rehabilitation exercises
using MediaPipe Pose + hysteresis state machine.

Usage:
    python kimore_rep_counter_demo.py

Change EXERCISE_NAME below (or pass as CLI arg) to select exercise.
Press 'q' to quit, 'r' to reset rep count.
"""

import sys
import cv2
import mediapipe as mp
import numpy as np
import time

# Allow running from project root
sys.path.insert(0, ".")

from Rehab_Scorer_Coach.src.rep_counter_kimore import KimoreRepCounter

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils

# ================================
# SELECT EXERCISE (edit or pass as CLI arg)
# ================================
EXERCISE_CHOICES = [
    "arm_lifting",
    "lateral_trunk_tilt",
    "trunk_rotation",
    "pelvis_rotation",
    "squat",
]

EXERCISE_NAME = "arm_lifting"
if len(sys.argv) > 1:
    EXERCISE_NAME = sys.argv[1]

if EXERCISE_NAME not in EXERCISE_CHOICES:
    # Try fuzzy match
    for c in EXERCISE_CHOICES:
        if EXERCISE_NAME.lower().replace(" ", "_") in c:
            EXERCISE_NAME = c
            break
    else:
        print(f"Unknown exercise: {EXERCISE_NAME}")
        print(f"Choose from: {EXERCISE_CHOICES}")
        sys.exit(1)

print(f"RUNNING: {EXERCISE_NAME}")

# ================================
# UI SETTINGS
# ================================
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (0, 255, 0)
PANEL_COLOR = (0, 0, 0)
PANEL_ALPHA = 0.6


def draw_panel(frame, x, y, w, h, color=(0, 0, 0), alpha=0.6):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


# ================================
# INIT
# ================================
counter = KimoreRepCounter()
counter.reset(EXERCISE_NAME)

cap = cv2.VideoCapture(0)

with mp_pose.Pose(
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
) as pose:

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)

        rep_info = None
        if res.pose_landmarks:
            # Extract landmarks as (33, 3) numpy array
            landmarks = np.array(
                [[lm.x, lm.y, lm.z] for lm in res.pose_landmarks.landmark],
                dtype=np.float32,
            )

            # Count reps
            rep_info = counter.update_landmarks(EXERCISE_NAME, landmarks)

            # Draw skeleton
            mp_draw.draw_landmarks(frame, res.pose_landmarks, mp_pose.POSE_CONNECTIONS)

        # ── UI overlay ──
        reps = rep_info.reps if rep_info else counter.reps
        phase = rep_info.phase if rep_info else counter.phase
        note = rep_info.note if rep_info else ""

        draw_panel(frame, 15, 10, 620, 200, PANEL_COLOR, PANEL_ALPHA)

        cv2.putText(frame, f"Exercise: {EXERCISE_NAME}", (25, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, TEXT_COLOR, 2)
        cv2.putText(frame, f"Reps: {reps}", (25, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, ACCENT_COLOR, 3)
        cv2.putText(frame, f"Phase: {phase}", (25, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, TEXT_COLOR, 2)

        # Show signal details (truncate long notes)
        note_display = note[:80] if note else ""
        cv2.putText(frame, note_display, (25, 165),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)

        cv2.putText(frame, "q=quit  r=reset", (25, frame.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 2)

        cv2.imshow("Kimore Rep Counter", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("r"):
            counter.reset(EXERCISE_NAME)
            print(f"[RESET] {EXERCISE_NAME}")

cap.release()
cv2.destroyAllWindows()
print(f"\nFinal count: {counter.reps} reps")
