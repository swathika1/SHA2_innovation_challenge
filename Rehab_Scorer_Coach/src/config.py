from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    repo_root: Path = Path(__file__).resolve().parents[1]
    assets_dir: Path = repo_root / "assets"
    models_dir: Path = repo_root / "models"

    # --- Pose backend switch ---
    use_openpose: bool = True
    openpose_url: str = "http://127.0.0.1:9001/openpose"

    # If you still keep mediapipe around, fine:
    pose_model_path: Path = assets_dir / "pose_landmarker_lite.task"

    # --- Score model (regression) ---
    keras_model_path: Path = models_dir / "poseformer_transformer_model.keras"
    x_scaler_path: Path = models_dir / "x_scaler.pkl"
    y_map_path: Path = models_dir / "y_map.pkl"

    # --- Exercise model (classification) ---
    exercise_detection_model_path: Path = models_dir / "kimore_exercise_detection_model.keras"
    exercise_mapping_path: Path = models_dir / "kimore_label_map.json"
    exercise_scaler_path: Path = models_dir / "x_scaler.pkl"

    # Expected model input sizes (MUST match training)
    target_timesteps: int = 100
    feature_dim: int = 100  # 25 keypoints * (x,y,z,score)

    # Live capture
    sample_every_seconds: float = 2.0

    # Trigger logic settings (score alerts)
    smoothing_window: int = 5
    threshold_low: float = 22.0
    threshold_high: float = 26.0
    cooldown_seconds: float = 12.0
    
    openpose_url: str = "http://127.0.0.1:9001"
