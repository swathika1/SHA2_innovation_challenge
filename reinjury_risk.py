"""
Re-Injury Risk Detection Engine
================================
Analyses a patient's recent session history across four biomechanical signals
and returns a composite risk score with a human-readable explanation.

Signals
-------
1. Form score trend       – linear slope of quality_score over last 8 sessions
2. Within-session fatigue – first-third vs last-third frame-score drop %
3. Pain escalation        – linear slope of pain_before over last 6 sessions
4. Effort-quality gap     – high effort_level paired with low quality_score

Risk levels
-----------
green  (0-3)  : on track
yellow (4-5)  : monitor closely
orange (6-8)  : notify therapist
red    (9+)   : pause progression, flag for manual review
"""

from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slope(values: list[float]) -> float:
    """Return the least-squares slope of a sequence (index as x-axis)."""
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    # Remove NaNs
    mask = ~np.isnan(y)
    if mask.sum() < 2:
        return 0.0
    x, y = x[mask], y[mask]
    return float(np.polyfit(x, y, 1)[0])


def _score_form_trend(slope: float) -> tuple[int, str]:
    """
    Convert quality_score slope → signal points + description.
    Slope is in quality-score-units per session.
    """
    if slope >= 0:
        return 0, None
    if slope >= -1.5:
        return 1, f"Form score declining slowly ({slope:+.1f} pts/session)"
    if slope >= -3.5:
        return 2, f"Form score declining steadily ({slope:+.1f} pts/session)"
    return 3, f"Form score falling sharply ({slope:+.1f} pts/session)"


def _score_fatigue(drop_pct: float | None) -> tuple[int, str]:
    """
    Convert within-session fatigue drop % → signal points + description.
    drop_pct = (first_avg - last_avg) / first_avg * 100
    """
    if drop_pct is None:
        return 0, None
    if drop_pct < 10:
        return 0, None
    if drop_pct < 20:
        return 1, f"Mild in-session fatigue ({drop_pct:.0f}% score drop by final set)"
    if drop_pct < 35:
        return 2, f"Moderate in-session fatigue ({drop_pct:.0f}% score drop by final set)"
    return 3, f"Severe in-session fatigue ({drop_pct:.0f}% score drop — body struggling under load)"


def _score_pain_trend(slope: float) -> tuple[int, str]:
    """
    Convert pain_before slope → signal points + description.
    Slope is in pain-units per session (0-10 scale).
    """
    if slope <= 0:
        return 0, None
    if slope < 0.3:
        return 1, f"Pain slowly increasing ({slope:+.2f} pts/session)"
    if slope < 0.7:
        return 2, f"Pain rising across sessions ({slope:+.2f} pts/session)"
    return 3, f"Pain escalating significantly ({slope:+.2f} pts/session)"


def _score_asymmetry(asymmetry_avg: float | None, asymmetry_trend_slope: float) -> tuple[int, str]:
    """
    Score based on average asymmetry AND whether it is growing.
    asymmetry_avg  : average asymmetry_pct across recent sessions
    asymmetry_trend_slope: slope of per-session avg asymmetry over time
    """
    if asymmetry_avg is None:
        return 0, None
    # Severity of current asymmetry
    if asymmetry_avg < 10:
        base = 0
    elif asymmetry_avg < 18:
        base = 1
    elif asymmetry_avg < 28:
        base = 2
    else:
        base = 3
    # Bonus point if it is getting worse
    if asymmetry_trend_slope > 1.5 and base < 3:
        base += 1
    if base == 0:
        return 0, None
    trend_note = f", rising +{asymmetry_trend_slope:.1f}%/session" if asymmetry_trend_slope > 1.5 else ""
    return min(base, 3), f"Left/right asymmetry at {asymmetry_avg:.0f}%{trend_note} (healthy target: <10%)"


def _score_rom(rom_avg: float | None, rom_slope: float) -> tuple[int, str]:
    """
    Score based on whether average joint angle (knee) is trending upward.
    A rising angle means the patient is achieving LESS flexion — ROM is shrinking.
    rom_avg   : average rom_angle (degrees) across recent sessions
    rom_slope : slope of per-session avg rom_angle (positive = less flexion over time)
    """
    if rom_avg is None:
        return 0, None
    # Only flag if ROM is genuinely declining (slope positive = less flexion)
    if rom_slope < 1.0:
        return 0, None
    if rom_slope < 3.0:
        return 1, f"Knee flexion slowly reducing ({rom_avg:.0f}° avg, slope +{rom_slope:.1f}°/session)"
    if rom_slope < 6.0:
        return 2, f"Knee flexion declining ({rom_avg:.0f}° avg, slope +{rom_slope:.1f}°/session)"
    return 3, f"Significant ROM loss — patient reaching less depth each session ({rom_avg:.0f}° avg)"


def _score_effort_quality_gap(effort_avg: float, quality_avg: float) -> tuple[int, str]:
    """
<<<<<<< Updated upstream
    Effort is 0-10, quality is 0-100. Normalise effort to same scale.
    A large gap means the patient is working hard but movement quality is poor.
    """
    effort_norm = effort_avg * 10   # 0-100
    gap = effort_norm - quality_avg
    if gap < 10:
        return 0, None
    if gap < 20:
        return 1, f"Slight effort-quality mismatch (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/100)"
    if gap < 35:
        return 2, f"Patient working hard but form declining (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/100)"
    return 3, f"Large effort-quality gap — compensatory movement likely (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/100)"
=======
    Effort is 0-10, quality is 0-50. Normalise effort to same scale.
    A large gap means the patient is working hard but movement quality is poor.
    """
    effort_norm = effort_avg * 5   # 0-50
    gap = effort_norm - quality_avg
    if gap < 5:
        return 0, None
    if gap < 10:
        return 1, f"Slight effort-quality mismatch (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/50)"
    if gap < 17.5:
        return 2, f"Patient working hard but form declining (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/50)"
    return 3, f"Large effort-quality gap — compensatory movement likely (effort {effort_avg:.1f}/10, form {quality_avg:.0f}/50)"
>>>>>>> Stashed changes


def _risk_level(score: int) -> str:
    if score <= 3:
        return "green"
    if score <= 5:
        return "yellow"
    if score <= 8:
        return "orange"
    return "red"


def _risk_label(level: str) -> str:
    return {"green": "On Track", "yellow": "Monitor Closely",
            "orange": "Notify Therapist", "red": "Pause Progression"}[level]


# ---------------------------------------------------------------------------
# Medical history scoring
# ---------------------------------------------------------------------------

# Chronic conditions that impair tissue healing or load tolerance.
# Matched case-insensitively as substrings against medical_conditions.name.
_HEALING_RISK_CONDITIONS = {
    "diabetes":          1.0,  # Microvascular disease slows wound/tissue healing
    "hypertension":      0.5,  # Reduces peripheral circulation and recovery capacity
    "obesity":           0.5,  # Increased joint load and systemic inflammation
    "osteoporosis":      1.0,  # Reduced bone density raises fracture re-injury risk
    "rheumatoid":        1.0,  # Autoimmune-driven joint degradation
    "lupus":             0.5,  # Connective tissue involvement increases injury susceptibility
    "hypothyroid":       0.5,  # Slows metabolic recovery and muscle regeneration
}

# Family history conditions that raise hereditary tissue risk.
_FAMILY_RISK_CONDITIONS = {
    "osteoporosis":           1.0,  # Hereditary bone-density deficit
    "connective tissue":      1.0,  # Heritable disorders (e.g. Marfan, EDS) weaken tendons/ligaments
    "rheumatoid":             0.5,  # Genetic predisposition to inflammatory joint disease
    "cardiovascular":         0.5,  # Reduced healing perfusion risk is partly heritable
    "diabetes":               0.5,  # Type-2 heritability impacts healing potential
}

# Maximum additive points the medical history layer can contribute.
# Keeps history as a contextual modifier without overriding biomechanical signals.
_HISTORY_MAX_PTS = 4.0


def _score_medical_history(history: dict | None) -> tuple[float, list[str]]:
    """
    Score the patient's structured medical history and return additive risk
    points and human-readable signal strings.

    If history is None or empty, returns (0, []) — the existing biomechanical
    score is left unchanged.

    Parameters
    ----------
    history : dict with optional keys:
        conditions    : list of dicts {name, onset_year}
        injuries      : list of dicts {body_region, related_to_current,
                                       recovery_complete, recurrence}
        surgeries     : list of dicts {body_region}
        family_history: list of dicts {condition}

    Returns
    -------
    (pts, signal_strings) — pts is a float capped at _HISTORY_MAX_PTS
    """
    if not history:
        return 0.0, []

    pts = 0.0
    signals: list[str] = []

    # ── Chronic conditions ─────────────────────────────────────────────── #
    conditions = history.get("conditions") or []
    for cond in conditions:
        name_lower = (cond.get("name") or "").lower()
        for keyword, weight in _HEALING_RISK_CONDITIONS.items():
            if keyword in name_lower:
                pts += weight
                signals.append(
                    f"{cond['name']} (chronic condition — {keyword} impairs healing, +{weight:.1f} pts)"
                )
                break  # one match per condition record is enough

    # ── Prior injuries ────────────────────────────────────────────────── #
    injuries = history.get("injuries") or []
    for inj in injuries:
        region = inj.get("body_region", "unspecified region")

        # Incomplete recovery on the same body region is a primary risk driver.
        # Clinical basis: unresolved tissue damage significantly increases
        # the likelihood of re-injury under renewed mechanical load.
        if inj.get("related_to_current") and not inj.get("recovery_complete"):
            pts += 2.0
            signals.append(
                f"Incomplete recovery — prior {region} injury related to current problem (+2.0 pts)"
            )

        # Recurrence flag: prior re-injury is the single strongest predictor
        # of future re-injury (higher than biomechanical signals alone).
        if inj.get("recurrence"):
            pts += 2.0
            signals.append(
                f"Recurrence history — {region} injury has occurred before (+2.0 pts)"
            )

    # ── Prior surgeries on the same body region ───────────────────────── #
    # Each surgery leaves scar tissue and alters biomechanics; the effect
    # is cumulative but diminishing, so we cap the total contribution at +2.
    surgeries = history.get("surgeries") or []
    surgery_pts = min(len(surgeries) * 0.5, 2.0)
    if surgery_pts > 0:
        pts += surgery_pts
        signals.append(
            f"{len(surgeries)} prior surger{'y' if len(surgeries) == 1 else 'ies'} on record "
            f"— cumulative scar tissue and biomechanical changes (+{surgery_pts:.1f} pts)"
        )

    # ── Family history of hereditary conditions ──────────────────────── #
    family = history.get("family_history") or []
    for entry in family:
        cond_lower = (entry.get("condition") or "").lower()
        for keyword, weight in _FAMILY_RISK_CONDITIONS.items():
            if keyword in cond_lower:
                relation = entry.get("relation", "family member")
                pts += weight
                signals.append(
                    f"Family history: {entry['condition']} ({relation}) "
                    f"— hereditary tissue risk factor (+{weight:.1f} pts)"
                )
                break

    # Cap total history contribution
    pts = min(pts, _HISTORY_MAX_PTS)
    return pts, signals


def _fetch_medical_history(patient_id: int, query_fn: "Callable") -> dict:
    """
    Pull all five medical history categories for a patient in one pass.
    Returns a dict keyed by category; values are lists of dicts.
    Returns empty dict if the medical history tables do not yet exist.
    """
    try:
        conditions = query_fn(
            "SELECT name, onset_year FROM medical_conditions WHERE patient_id = ?",
            (patient_id,)
        ) or []
        injuries = query_fn(
            """SELECT body_region, related_to_current, recovery_complete, recurrence
               FROM medical_injuries WHERE patient_id = ?""",
            (patient_id,)
        ) or []
        surgeries = query_fn(
            "SELECT body_region FROM medical_surgeries WHERE patient_id = ?",
            (patient_id,)
        ) or []
        family = query_fn(
            "SELECT condition, relation FROM medical_family_history WHERE patient_id = ?",
            (patient_id,)
        ) or []
        return {
            "conditions":     [dict(r) for r in conditions],
            "injuries":       [dict(r) for r in injuries],
            "surgeries":      [dict(r) for r in surgeries],
            "family_history": [dict(r) for r in family],
        }
    except Exception:
        # Tables may not exist yet (pre-migration). Degrade gracefully.
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_patient_risk(patient_id: int, query_fn: "Callable") -> dict:
    """
    Run the full re-injury risk analysis for a single patient.

    Parameters
    ----------
    patient_id : int
    query_fn   : the app's query_db function (returns list of sqlite3.Row or [])

    Returns
    -------
    dict with keys:
        risk_level      : 'green' | 'yellow' | 'orange' | 'red'
        risk_label      : human-readable level name
        risk_score      : int 0-12
        signals_fired   : int count of signals that contributed points
        signal_details  : list of triggered signal strings
        explanation     : short therapist-facing summary string
        trend_data      : dict of lists for charting
        has_data        : bool (False when not enough sessions to judge)
    """

    # ------------------------------------------------------------------ #
    # 1. Pull recent sessions (last 8 completed)
    # ------------------------------------------------------------------ #
    recent_sessions = query_fn(
        """
        SELECT quality_score, pain_before, pain_after, effort_level, completed_at
        FROM sessions
        WHERE patient_id = ?
          AND completed_at IS NOT NULL
        ORDER BY completed_at ASC
        LIMIT 8
        """,
        (patient_id,)
    ) or []

    if len(recent_sessions) < 3:
        return {
            "risk_level": "green",
            "risk_label": "On Track",
            "risk_score": 0,
            "signals_fired": 0,
            "signal_details": [],
            "explanation": "Not enough session data yet to assess re-injury risk. Check back after 3+ completed sessions.",
            "trend_data": {},
            "has_data": False,
        }

    quality_scores  = [float(r["quality_score"] or 0)  for r in recent_sessions]
    pain_befores    = [float(r["pain_before"]   or 0)  for r in recent_sessions]
    effort_levels   = [float(r["effort_level"]  or 5)  for r in recent_sessions]
    dates           = [r["completed_at"]               for r in recent_sessions]

    # ------------------------------------------------------------------ #
    # 2. Signal 1 — Form score trend
    # ------------------------------------------------------------------ #
    form_slope = _slope(quality_scores)
    pts_form, msg_form = _score_form_trend(form_slope)

    # ------------------------------------------------------------------ #
    # 3. Signal 2 — Within-session fatigue + Asymmetry + ROM
    #    All derived from session_frames of the last 3 sessions
    # ------------------------------------------------------------------ #
    from collections import defaultdict

    last_3_session_ids = query_fn(
        """
        SELECT id FROM sessions
        WHERE patient_id = ? AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 3
        """,
        (patient_id,)
    ) or []

    fatigue_drop_pct = None
    # Per-session biomechanics averages (for trend computation)
    session_asymmetry_avgs: list[float] = []
    session_rom_avgs: list[float] = []

    if last_3_session_ids:
        id_list = ",".join(str(r["id"]) for r in last_3_session_ids)
        frames = query_fn(
            f"""
            SELECT session_id, score, asymmetry_pct, rom_angle
            FROM session_frames
            WHERE patient_id = ?
              AND session_id IN ({id_list})
            ORDER BY session_id, id
            """,
            (patient_id,)
        ) or []

        session_data: dict[int, dict] = defaultdict(lambda: {"scores": [], "asym": [], "rom": []})
        for f in frames:
            sid = f["session_id"]
            session_data[sid]["scores"].append(float(f["score"] or 0))
            if f["asymmetry_pct"] is not None:
                session_data[sid]["asym"].append(float(f["asymmetry_pct"]))
            if f["rom_angle"] is not None:
                session_data[sid]["rom"].append(float(f["rom_angle"]))

        drops = []
        for sid, d in session_data.items():
            scores = d["scores"]
            if len(scores) >= 6:
                third = max(1, len(scores) // 3)
                first_avg = np.mean(scores[:third])
                last_avg  = np.mean(scores[-third:])
                if first_avg > 0:
                    drops.append((first_avg - last_avg) / first_avg * 100)
            if d["asym"]:
                session_asymmetry_avgs.append(float(np.mean(d["asym"])))
            if d["rom"]:
                session_rom_avgs.append(float(np.mean(d["rom"])))

        if drops:
            fatigue_drop_pct = float(np.mean(drops))

    pts_fatigue, msg_fatigue = _score_fatigue(fatigue_drop_pct)

    # ------------------------------------------------------------------ #
    # 3b. Signal — Asymmetry trend
    # ------------------------------------------------------------------ #
    asym_avg   = float(np.mean(session_asymmetry_avgs)) if session_asymmetry_avgs else None
    asym_slope = _slope(session_asymmetry_avgs) if len(session_asymmetry_avgs) >= 2 else 0.0
    pts_asym, msg_asym = _score_asymmetry(asym_avg, asym_slope)

    # ------------------------------------------------------------------ #
    # 3c. Signal — ROM trend (rising angle = less flexion = ROM loss)
    # ------------------------------------------------------------------ #
    rom_avg   = float(np.mean(session_rom_avgs)) if session_rom_avgs else None
    rom_slope = _slope(session_rom_avgs) if len(session_rom_avgs) >= 2 else 0.0
    pts_rom, msg_rom = _score_rom(rom_avg, rom_slope)

    # ------------------------------------------------------------------ #
    # 4. Signal 3 — Pain escalation trend
    # ------------------------------------------------------------------ #
    pain_slope = _slope(pain_befores)
    pts_pain, msg_pain = _score_pain_trend(pain_slope)

    # ------------------------------------------------------------------ #
    # 5. Signal 4 — Effort-quality gap (last 3 sessions)
    # ------------------------------------------------------------------ #
    recent_efforts  = effort_levels[-3:]
    recent_quality  = quality_scores[-3:]
    effort_avg  = float(np.mean(recent_efforts))
    quality_avg = float(np.mean(recent_quality))
    pts_gap, msg_gap = _score_effort_quality_gap(effort_avg, quality_avg)

    # ------------------------------------------------------------------ #
    # 6. Medical history — optional additive layer
    # ------------------------------------------------------------------ #
    history = _fetch_medical_history(patient_id, query_fn)
    pts_history, msgs_history = _score_medical_history(history)

    # ------------------------------------------------------------------ #
    # 7. Composite score
    # Weights: form + asymmetry + pain are primary biomechanical signals
    #          ROM + fatigue are secondary, effort-gap is contextual
    #          medical history is additive, capped at _HISTORY_MAX_PTS
    # ------------------------------------------------------------------ #
    raw_score = (
        pts_form    * 1.4 +
        pts_asym    * 1.3 +
        pts_pain    * 1.2 +
        pts_rom     * 1.1 +
        pts_fatigue * 1.0 +
        pts_gap     * 0.8 +
        pts_history          # already capped inside _score_medical_history
    )
    risk_score = min(12, round(raw_score))

    signal_details = [m for m in [msg_form, msg_asym, msg_pain, msg_rom, msg_fatigue, msg_gap] if m]
    signal_details += msgs_history
    signals_fired  = sum(1 for p in [pts_form, pts_asym, pts_pain, pts_rom, pts_fatigue, pts_gap, pts_history] if p > 0)
    level = _risk_level(risk_score)

    # ------------------------------------------------------------------ #
    # 8. Build explanation
    # ------------------------------------------------------------------ #
    if not signal_details:
        explanation = "All signals look healthy. Patient is progressing well — no re-injury risk detected."
    else:
        parts = ". ".join(signal_details)
        if level == "yellow":
            action = "Monitor closely before increasing load."
        elif level == "orange":
            action = "Consider reviewing exercise load before next session."
        else:
            action = "Recommend pausing progression and conducting a manual review."
        explanation = f"{parts}. {action}"

    # ------------------------------------------------------------------ #
    # 9. Trend data for charting
    # ------------------------------------------------------------------ #
    trend_data = {
        "dates":          dates,
        "quality_scores": quality_scores,
        "pain_befores":   pain_befores,
        "effort_levels":  effort_levels,
        "fatigue_drop_pct": round(fatigue_drop_pct, 1) if fatigue_drop_pct is not None else None,
    }

    return {
        "risk_level":     level,
        "risk_label":     _risk_label(level),
        "risk_score":     risk_score,
        "signals_fired":  signals_fired,
        "signal_details": signal_details,
        "explanation":    explanation,
        "trend_data":     trend_data,
        "has_data":       True,
        # Individual signal breakdown (useful for detailed views)
        "_signals": {
            "form":      {"pts": pts_form,    "slope": round(form_slope, 2)},
            "asymmetry": {"pts": pts_asym,    "avg_pct": round(asym_avg, 1) if asym_avg is not None else None, "slope": round(asym_slope, 2)},
            "pain":      {"pts": pts_pain,    "slope": round(pain_slope, 2)},
            "rom":       {"pts": pts_rom,     "avg_angle": round(rom_avg, 1) if rom_avg is not None else None, "slope": round(rom_slope, 2)},
            "fatigue":   {"pts": pts_fatigue, "drop_pct": round(fatigue_drop_pct, 1) if fatigue_drop_pct is not None else None},
            "gap":       {"pts": pts_gap,     "effort_avg": round(effort_avg, 1), "quality_avg": round(quality_avg, 1)},
            "history":   {"pts": round(pts_history, 2), "signals": msgs_history},
        },
        "raw_score": round(raw_score, 4),
    }
