import cv2
import os
import time

SAVE_ROOT = "exercise_dataset"
CLASS_NAME = "ideal" #"pelvis_rotation" #"trunk_rotation"#"lateral_trunk_tilt" #"lifting_of_arms" #"squat"  # change per run
FPS = 5               # capture 5 frames per second
DURATION = 120        # seconds per exercise

save_path = os.path.join(SAVE_ROOT, CLASS_NAME)
os.makedirs(save_path, exist_ok=True)

cap = cv2.VideoCapture(0)

frame_interval = 1.0 / FPS
start_time = time.time()
frame_count = 0

print("Recording...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    elapsed = time.time() - start_time
    if elapsed > DURATION:
        break

    cv2.imshow("Recording", frame)

    # Save frame
    filename = os.path.join(save_path, f"{frame_count}.jpg")
    cv2.imwrite(filename, frame)
    frame_count += 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    time.sleep(frame_interval)

cap.release()
cv2.destroyAllWindows()

print("Done.")