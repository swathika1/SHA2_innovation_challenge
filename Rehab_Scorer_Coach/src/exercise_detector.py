# Rehab_Scorer_Coach/src/exercise_model_infer.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import keras
import joblib

from Rehab_Scorer_Coach.src.config import AppConfig
from Rehab_Scorer_Coach.src.model_infer import TransformerBlock  # required if your model uses it


@dataclass
class ExercisePred:
    name: str                 # thresholded (may be "unknown")
    confidence: float         # best_p
    best_label_raw: str       # argmax label without thresholding
    probs: Dict[str, float]   # label->prob
    best_id: int


class ExerciseModelInfer:
    """
    Temporal pose->exercise classifier inference.
    Expects (1, T, F) float32 matching training.
    """

    def __init__(self, cfg: Optional[AppConfig] = None, verbose: bool = True):
        self.cfg = cfg or AppConfig()

        model_path = Path(self.cfg.exercise_detection_model_path)
        label_map_path = Path(self.cfg.exercise_mapping_path)
        scaler_path = Path(self.cfg.exercise_scaler_path) if getattr(self.cfg, "exercise_scaler_path", None) else None

        self.T = int(self.cfg.exercise_T)
        self.F = int(self.cfg.exercise_F)
        self.conf_threshold = float(getattr(self.cfg, "exercise_conf_threshold", 0.60))

        if not model_path.exists():
            raise FileNotFoundError(f"[ExerciseModelInfer] Model not found: {model_path}")
        if not label_map_path.exists():
            raise FileNotFoundError(f"[ExerciseModelInfer] Label map not found: {label_map_path}")

        label_map = json.loads(label_map_path.read_text())
        self.id_to_label = {int(k): v for k, v in label_map.items()}
        self.num_classes = len(self.id_to_label)

        self.scaler = None
        if scaler_path is not None and scaler_path.exists():
            self.scaler = joblib.load(str(scaler_path))

        self.model = keras.models.load_model(
            str(model_path),
            compile=False,
            safe_mode=False,
            custom_objects={"TransformerBlock": TransformerBlock},
        )

        # ---------------- HARD VALIDATION ----------------
        # Ensure model is classifier: output dim == num_classes
        out_shape = self.model.output_shape  # e.g. (None, C) or (None, T, C)
        in_shape = self.model.input_shape

        if verbose:
            print("\n[ExerciseModelInfer] LOADED EXERCISE MODEL")
            print("  model_path:", model_path)
            print("  input_shape:", in_shape)
            print("  output_shape:", out_shape)
            print("  num_classes(from label_map):", self.num_classes)
            print("  expected window:", (1, self.T, self.F))
            print("  conf_threshold:", self.conf_threshold)
            print()

        # Support (None, C) only for now. If your model outputs (None, T, C), we can adapt later.
        if isinstance(out_shape, (list, tuple)) and len(out_shape) == 2:
            out_dim = int(out_shape[-1])
        else:
            raise ValueError(
                f"[ExerciseModelInfer] Unexpected output_shape={out_shape}. "
                f"Expected (None, C). If your model outputs sequences, tell me and I’ll adapt."
            )

        if out_dim != self.num_classes:
            raise ValueError(
                f"[ExerciseModelInfer] WRONG MODEL LOADED OR WRONG LABEL MAP.\n"
                f"  Model output dim = {out_dim}\n"
                f"  Label map classes = {self.num_classes}\n"
                f"Fix: point exercise_detection_model_path to the correct classifier .keras "
                f"(with softmax over classes), and ensure mapping json matches training."
            )
        # ------------------------------------------------

    def predict_window(self, X_1: np.ndarray) -> ExercisePred:
        if X_1.ndim != 3 or X_1.shape[0] != 1:
            raise ValueError(f"Expected (1,T,F), got {X_1.shape}")
        if X_1.shape[1] != self.T or X_1.shape[2] != self.F:
            raise ValueError(f"Expected (1,{self.T},{self.F}), got {X_1.shape}")

        X = X_1.astype(np.float32)

        if self.scaler is not None:
            Xr = X.reshape(-1, self.F)
            Xr = self.scaler.transform(Xr)
            X = Xr.reshape(1, self.T, self.F).astype(np.float32)

        probs = self.model.predict(X, verbose=0)[0]  # (C,)
        probs = np.asarray(probs, dtype=np.float32)

        best_id = int(np.argmax(probs))
        best_p = float(probs[best_id])

        best_label_raw = self.id_to_label.get(best_id, "unknown")
        probs_dict = {self.id_to_label[i]: float(probs[i]) for i in range(len(probs))}

        # thresholded name
        name = best_label_raw
        if best_p < self.conf_threshold:
            name = "unknown"

        return ExercisePred(
            name=name,
            confidence=best_p,
            best_label_raw=best_label_raw,
            probs=probs_dict,
            best_id=best_id,
        )