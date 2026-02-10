from dataclasses import dataclass
from pathlib import Path

@dataclass
class AppConfig:
    repo_root: Path = Path(__file__).resolve().parents[1]
    assets_dir: Path = repo_root / "assets"
    models_dir: Path = repo_root / "models"

    pose_model_path: Path = assets_dir / "pose_landmarker_lite.task"

    keras_model_path: Path = models_dir / "poseformer_transformer_model.keras"
    x_scaler_path: Path = models_dir / "x_scaler.pkl"
    y_map_path: Path = models_dir / "y_map.pkl"  # contains {"a":..., "b":...}

    # Expected model input sizes
    target_timesteps: int = 100
    feature_dim: int = 100  # 25 landmarks * (x,y,z,visibility/presence)

    # Live capture settings
    sample_every_seconds: float = 2.0

    # Trigger logic settings (reduce spam due to MAE/noise)
    smoothing_window: int = 5          # rolling mean over last N scores
    threshold_low: float = 22.0        # enter alert if smoothed score < low
    threshold_high: float = 26.0       # exit alert only if smoothed score > high
    cooldown_seconds: float = 12.0     # time between spoken advice