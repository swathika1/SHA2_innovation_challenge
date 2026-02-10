import base64
import cv2
import numpy as np

def frame_to_jpeg_base64(bgr_frame: np.ndarray) -> str:
    ok, buf = cv2.imencode(".jpg", bgr_frame)
    if not ok:
        raise ValueError("Failed to encode frame as JPEG")
    return base64.b64encode(buf.tobytes()).decode("utf-8")

def get_correction_advice_from_vision_llm(bgr_frame: np.ndarray, exercise_name: str = "exercise") -> str:
    """
    Replace this stub with SEA-LION Vision API call when access is ready.
    For now it returns a deterministic coaching suggestion.
    """
    _ = frame_to_jpeg_base64(bgr_frame)

    return (
        f"Your form for {exercise_name} looks off. "
        "Slow down slightly, brace your core, and keep a controlled range of motion. "
        "Keep knees aligned with toes and avoid leaning forward."
    )