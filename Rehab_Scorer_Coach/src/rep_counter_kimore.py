from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RepInfo:
    reps: int
    phase: str
    note: str


class KimoreRepCounter:
    """
    Rep counter interface expected by web_pipeline.py

    web_pipeline calls:
        rep_counter.reset(exercise_name)
        rep_counter.update(exercise_name, angles_dict)

    So we MUST support those exact signatures.
    """

    def __init__(self):
        self.exercise_name: str = "unknown"
        self.reps: int = 0
        self.phase: str = "idle"
        self._state: Dict[str, Any] = {}

    def reset(self, exercise_name: str = "unknown"):
        self.exercise_name = exercise_name or "unknown"
        self.reps = 0
        self.phase = "idle"
        self._state = {}

    def update(self, exercise_name: str, angles_dict: Dict[str, float]) -> RepInfo:
        """
        Parameters
        ----------
        exercise_name : str
            current detected/selected exercise name
        angles_dict : dict
            dictionary of angles/features computed from pose landmarks
            e.g. {"left_elbow": 123.4, "right_knee": 88.1, ...}

        Returns
        -------
        RepInfo
            contains reps count + phase + note
        """

        # Keep current exercise name updated
        if exercise_name and exercise_name != self.exercise_name:
            # If exercise changes mid-stream, reset internal state
            self.reset(exercise_name)

        # ---- PLACEHOLDER REP COUNTING ----
        # Right now this does NOT try to count reps.
        # It simply returns a stable object so your Flask app doesn't crash.
        # You can plug your actual Kimore rep logic here later.

        note = f"rep_counter placeholder | ex={self.exercise_name} | angles={len(angles_dict) if angles_dict else 0}"
        return RepInfo(reps=self.reps, phase=self.phase, note=note)