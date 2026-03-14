"""
Recovery Timeline Predictor
===========================
Rule-based heuristic model that estimates recovery progress and
predicted timeline using clinical baselines + behavioral adjustment.

Each MSK condition has an evidence-based recovery window (weeks).
The patient's actual adherence, quality trends, and pain trends
shift the estimate faster or slower.

Confidence grows with more completed sessions:
  < 3 sessions  → "Estimated"  (mostly baseline)
  3-10 sessions → "Projected"  (medium, trend-adjusted)
  10+ sessions  → "Predicted"  (higher confidence)
"""

from __future__ import annotations
from typing import Callable, Optional

# ── Evidence-based recovery windows (min_weeks, max_weeks) ──────────
CONDITION_RECOVERY_WEEKS: dict[str, tuple[int, int]] = {
    "Spine conditions":    (10, 18),
    "Joint disorders":     (8, 14),
    "Post-surgical rehab": (12, 20),
    "Sports injuries":     (8, 16),
    "Postural disorders":  (6, 12),
    "Muscle tightness":    (4, 10),
    "Neuromuscular rehab": (12, 24),
}

DEFAULT_RECOVERY_WEEKS = (8, 16)  # fallback for unknown conditions


def predict_recovery(patient_id: int, query_fn: Callable) -> dict:
    """
    Return a recovery prediction dict for a patient.

    Parameters
    ----------
    patient_id : int
        The user ID of the patient.
    query_fn : callable
        Database query helper  (query_db from main.py).

    Returns
    -------
    dict with keys:
        condition            : str
        current_week         : int
        total_weeks_estimate : int   (adjusted predicted total)
        progress_pct         : float (0-95, capped)
        remaining_weeks      : int
        confidence_label     : "Estimated" | "Projected" | "Predicted"
        confidence_pct       : int   (0-100)
        phase                : "Early" | "Building" | "Strengthening" | "Return to Activity"
        phase_pct            : float (progress within current phase)
        adjustments          : list[str]  (human-readable factor descriptions)
        milestones           : list[dict] (phase milestones with pct thresholds)
    """

    # ── 1. Get patient info ─────────────────────────────────────────
    patient = query_fn('''
        SELECT p.condition, p.current_week, p.adherence_rate,
               p.avg_quality_score, p.avg_pain_level,
               p.completed_sessions, p.surgery_date
        FROM patients p
        WHERE p.user_id = ?
    ''', (patient_id,), one=True)

    if not patient:
        return _empty_result("Unknown")

    condition = patient['condition'] or 'General Rehab'
    current_week = max(patient['current_week'] or 1, 1)
    adherence = patient['adherence_rate'] or 0.0
    avg_quality = patient['avg_quality_score'] or 0.0
    avg_pain = patient['avg_pain_level'] or 0.0

    # ── 2. Count real completed sessions ────────────────────────────
    row = query_fn(
        'SELECT COUNT(*) as cnt FROM sessions WHERE patient_id = ? AND completed_at IS NOT NULL',
        (patient_id,), one=True
    )
    total_completed = row['cnt'] if row else 0

    # ── 3. Get recent session trends (last 5) ──────────────────────
    recent = query_fn('''
        SELECT quality_score, pain_before, pain_after, effort_level
        FROM sessions
        WHERE patient_id = ? AND completed_at IS NOT NULL
        ORDER BY completed_at DESC
        LIMIT 5
    ''', (patient_id,))
    recent = [dict(r) for r in recent] if recent else []

    # ── 4. Baseline recovery window ────────────────────────────────
    min_wk, max_wk = CONDITION_RECOVERY_WEEKS.get(condition, DEFAULT_RECOVERY_WEEKS)
    base_weeks = (min_wk + max_wk) / 2.0

    # ── 5. Behavioral adjustment factor (0.80 – 1.30) ─────────────
    #    < 1.0 = faster recovery,  > 1.0 = slower recovery
    factor = 1.0
    adjustments: list[str] = []

    # 5a. Adherence impact (strongest signal)
    if adherence >= 80:
        factor -= 0.10
        adjustments.append("High adherence (≥80%) — recovery accelerated")
    elif adherence >= 60:
        factor -= 0.03
        adjustments.append("Good adherence (≥60%) — on track")
    elif adherence >= 30:
        factor += 0.05
        adjustments.append("Moderate adherence — recovery may be slower")
    else:
        factor += 0.15
        adjustments.append("Low adherence (<30%) — recovery significantly delayed")

    # 5b. Quality score impact
    if avg_quality >= 37.5:
        factor -= 0.07
        adjustments.append("Excellent exercise quality — positive signal")
    elif avg_quality >= 27.5:
        factor -= 0.02
        adjustments.append("Good exercise quality")
    elif avg_quality >= 17.5:
        factor += 0.04
        adjustments.append("Below-average quality — may slow progress")
    elif total_completed > 0:
        factor += 0.10
        adjustments.append("Poor exercise quality — recovery delayed")

    # 5c. Pain trend (recent sessions)
    if len(recent) >= 2:
        pain_afters = [s['pain_after'] for s in recent if s.get('pain_after') is not None]
        if len(pain_afters) >= 2:
            # Compare most recent half vs older half
            mid = len(pain_afters) // 2
            recent_pain = sum(pain_afters[:mid]) / mid
            older_pain = sum(pain_afters[mid:]) / (len(pain_afters) - mid)
            if recent_pain < older_pain - 0.5:
                factor -= 0.05
                adjustments.append("Pain decreasing — good recovery signal")
            elif recent_pain > older_pain + 1.0:
                factor += 0.08
                adjustments.append("Pain increasing — recovery may be affected")

    # 5d. Quality trend (improving?)
    if len(recent) >= 3:
        quality_scores = [s['quality_score'] for s in recent if s.get('quality_score') is not None]
        if len(quality_scores) >= 3:
            first_half = quality_scores[len(quality_scores)//2:]
            second_half = quality_scores[:len(quality_scores)//2]
            if second_half and first_half:
                avg_newer = sum(second_half) / len(second_half)
                avg_older = sum(first_half) / len(first_half)
                if avg_newer > avg_older + 5:
                    factor -= 0.03
                    adjustments.append("Quality improving over recent sessions")
                elif avg_newer < avg_older - 10:
                    factor += 0.05
                    adjustments.append("Quality declining — may slow recovery")

    # Clamp factor
    factor = max(0.80, min(1.30, factor))

    # ── 6. Adjusted total weeks ────────────────────────────────────
    adjusted_weeks = round(base_weeks * factor)
    adjusted_weeks = max(min_wk, min(max_wk + 4, adjusted_weeks))  # keep within reasonable bounds

    # ── 7. Progress percentage ─────────────────────────────────────
    progress_pct = min(95.0, round((current_week / adjusted_weeks) * 100, 1))
    # If few sessions but many weeks, cap lower
    if total_completed < 3 and progress_pct > 30:
        progress_pct = min(progress_pct, 30.0)

    remaining_weeks = max(0, adjusted_weeks - current_week)

    # ── 8. Confidence ──────────────────────────────────────────────
    if total_completed < 3:
        confidence_label = "Estimated"
        confidence_pct = 35
    elif total_completed < 10:
        confidence_label = "Projected"
        confidence_pct = 55 + min(25, (total_completed - 3) * 4)
    else:
        confidence_label = "Predicted"
        confidence_pct = min(90, 75 + min(15, (total_completed - 10) * 2))

    # ── 9. Recovery phases ─────────────────────────────────────────
    phases = [
        {"name": "Early Recovery",       "range": (0, 25),  "icon": "fa-seedling",     "color": "#ef4444"},
        {"name": "Building Strength",    "range": (25, 50), "icon": "fa-dumbbell",     "color": "#f59e0b"},
        {"name": "Functional Recovery",  "range": (50, 75), "icon": "fa-person-walking","color": "#3b82f6"},
        {"name": "Return to Activity",   "range": (75, 100),"icon": "fa-flag-checkered","color": "#22c55e"},
    ]

    current_phase = phases[0]
    phase_progress = 0.0
    for p in phases:
        lo, hi = p["range"]
        if progress_pct >= lo:
            current_phase = p
            span = hi - lo
            phase_progress = min(100.0, ((progress_pct - lo) / span) * 100) if span > 0 else 100.0

    # ── 10. Milestones ─────────────────────────────────────────────
    milestones = []
    for p in phases:
        lo, hi = p["range"]
        milestone_pct = hi
        milestones.append({
            "name": p["name"],
            "target_pct": milestone_pct,
            "reached": progress_pct >= milestone_pct,
            "icon": p["icon"],
            "color": p["color"],
        })

    if not adjustments:
        adjustments.append("Baseline estimate — more sessions will improve accuracy")

    return {
        "condition":            condition,
        "current_week":         current_week,
        "total_weeks_estimate": adjusted_weeks,
        "recovery_range":       {"min": min_wk, "max": max_wk},
        "progress_pct":         progress_pct,
        "remaining_weeks":      remaining_weeks,
        "confidence_label":     confidence_label,
        "confidence_pct":       confidence_pct,
        "phase":                current_phase["name"],
        "phase_icon":           current_phase["icon"],
        "phase_color":          current_phase["color"],
        "phase_progress":       round(phase_progress, 1),
        "adjustment_factor":    round(factor, 2),
        "adjustments":          adjustments,
        "milestones":           milestones,
        "total_sessions_used":  total_completed,
    }


def _empty_result(condition: str) -> dict:
    """Return a safe default when no patient data exists."""
    min_wk, max_wk = CONDITION_RECOVERY_WEEKS.get(condition, DEFAULT_RECOVERY_WEEKS)
    return {
        "condition":            condition,
        "current_week":         1,
        "total_weeks_estimate": round((min_wk + max_wk) / 2),
        "recovery_range":       {"min": min_wk, "max": max_wk},
        "progress_pct":         0.0,
        "remaining_weeks":      round((min_wk + max_wk) / 2),
        "confidence_label":     "Estimated",
        "confidence_pct":       20,
        "phase":                "Early Recovery",
        "phase_icon":           "fa-seedling",
        "phase_color":          "#ef4444",
        "phase_progress":       0.0,
        "adjustment_factor":    1.0,
        "adjustments":          ["No session data yet — using clinical baseline"],
        "milestones":           [],
        "total_sessions_used":  0,
    }
