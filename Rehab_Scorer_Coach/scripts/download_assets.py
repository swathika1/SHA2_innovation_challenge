from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
OUT = ASSETS / "pose_landmarker_lite.task"

def main():
    if OUT.exists():
        print("Already exists:", OUT)
        return
    print("Downloading pose landmarker model...")
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    OUT.write_bytes(r.content)
    print("Saved:", OUT)

if __name__ == "__main__":
    main()