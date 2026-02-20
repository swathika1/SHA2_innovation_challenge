# Rehab_Scorer_Coach/src/exercise_model_infer.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import numpy as np
import keras
import joblib

from Rehab_Scorer_Coach.src.config import AppConfig


@dataclass
class ExercisePred:
    """
    ALWAYS-RAW prediction object (no threshold gating).
    """
    # raw best label (argmax)
    best_label_raw: str
    best_id: int
    confidence: float  # best prob

    # convenient alias for UI
    name: str

    # full probs as dict + full vector
    probs: Dict[str, float]
    probs_vector: List[float]

    # top-k
    topk: List[Tuple[str, float]]


class ExerciseModelInfer:
    """
    Temporal pose->exercise classifier inference.
    Expects (1, T, F).
    """
    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or AppConfig()

        model_path = Path(self.cfg.exercise_detection_model_path)
        label_map_path = Path(self.cfg.exercise_mapping_path)

        scaler_path = None
        if getattr(self.cfg, "exercise_scaler_path", None):
            scaler_path = Path(self.cfg.exercise_scaler_path)

        if not model_path.exists():
            raise FileNotFoundError(f"exercise_detection_model_path not found: {model_path}")
        if not label_map_path.exists():
            raise FileNotFoundError(f"exercise_mapping_path not found: {label_map_path}")

        # IMPORTANT:
        # Your exercise model is Conv1D-based, so it should NOT require TransformerBlock.
        # Still, safe_mode=False is fine. We do NOT pass custom_objects unless needed.
        try:
            self.model = keras.models.load_model(
                str(model_path),
                compile=False,
                safe_mode=False,
            )
        except Exception:
            # fallback if some environment saved with legacy custom objects
            # (won't break conv models; just provides compatibility)
            from Rehab_Scorer_Coach.src.model_infer import TransformerBlock  # noqa: F401
            self.model = keras.models.load_model(
                str(model_path),
                compile=False,
                safe_mode=False,
                custom_objects={"TransformerBlock": TransformerBlock},
            )

        label_map = json.loads(label_map_path.read_text())
        self.id_to_label = {int(k): v for k, v in label_map.items()}

        self.T = int(getattr(self.cfg, "target_timesteps", 100))
        self.F = int(getattr(self.cfg, "feature_dim", 100))

        self.scaler = None
        if scaler_path is not None and scaler_path.exists():
            self.scaler = joblib.load(str(scaler_path))

        # just for logging
        print("[EX_MODEL] model_path:", str(model_path))
        print("[EX_MODEL] output_dim:", int(self.model.output_shape[-1]))
        print("[EX_MODEL] T,F:", self.T, self.F)
        print("[EX_MODEL] id_to_label:", self.id_to_label)

    def _apply_scaler(self, X: np.ndarray) -> np.ndarray:
        if self.scaler is None:
            return X
        Xr = X.reshape(-1, self.F)
        Xr = self.scaler.transform(Xr)
        return Xr.reshape(1, self.T, self.F).astype(np.float32)

    def predict_window(self, X_1: np.ndarray, top_k: int = 5, debug: bool = False) -> ExercisePred:
        """
        Returns ALWAYS-RAW:
        - best_label_raw always argmax label
        - name == best_label_raw (no thresholding / no unknown)
        - probs_vector always present
        """
        if not (isinstance(X_1, np.ndarray) and X_1.ndim == 3 and X_1.shape[0] == 1):
            raise ValueError(f"Expected numpy array (1,T,F), got {type(X_1)} shape={getattr(X_1,'shape',None)}")
        if X_1.shape[1] != self.T or X_1.shape[2] != self.F:
            raise ValueError(f"Expected (1,{self.T},{self.F}), got {X_1.shape}")

        X = X_1.astype(np.float32)
        X = self._apply_scaler(X)

        probs = self.model.predict(X, verbose=0)[0]  # (C,)
        probs = np.asarray(probs, dtype=np.float32)

        # safety: renormalize if numeric weirdness
        s = float(np.sum(probs))
        if not np.isfinite(s) or s <= 0:
            # fallback to uniform (prevents crashes)
            probs = np.ones_like(probs, dtype=np.float32) / float(len(probs))
        else:
            probs = probs / s

        best_id = int(np.argmax(probs))
        best_p = float(probs[best_id])
        best_label_raw = self.id_to_label.get(best_id, f"class_{best_id}")

        # dict + vector
        probs_vector = [float(probs[i]) for i in range(len(probs))]
        probs_dict = {self.id_to_label.get(i, f"class_{i}"): float(probs[i]) for i in range(len(probs))}

        # top-k
        k = min(int(top_k), len(probs))
        top_ids = np.argsort(-probs)[:k]
        topk = [(self.id_to_label.get(int(i), f"class_{int(i)}"), float(probs[int(i)])) for i in top_ids]

        if debug:
            print("[EX_MODEL] probs=", probs_vector, "sum=", float(np.sum(probs)))
            print(f"[EX_MODEL] argmax={best_id} label={best_label_raw} p={best_p:.6f} topk={topk}")

        return ExercisePred(
            best_label_raw=best_label_raw,
            best_id=best_id,
            confidence=best_p,
            name=best_label_raw,  # <- ALWAYS RAW, NO THRESHOLDING
            probs=probs_dict,
            probs_vector=probs_vector,
            topk=topk,
        )