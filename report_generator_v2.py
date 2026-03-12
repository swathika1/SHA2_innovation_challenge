"""
report_generator.py - Generate attractive PDF medical rehabilitation reports
with LLM-powered insights using Groq.

Produces a professional multi-page report covering:
  - Patient info and session metadata
  - Overall statistics (quality score, pain, effort, duration)
  - Per-exercise breakdown table
  - LLM-generated per-exercise feedback and improvement tips
  - Frame-level score timeline chart
  - Detailed performance metrics
  - LLM-generated concise session summary with center-visit recommendation
  - Professional header/footer with clinic logo
"""

import io
import os
from datetime import datetime
from collections import defaultdict
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.lineplots import LinePlot

# --- Groq LLM ---
try:
    from groq import Groq as _Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

# ====================== colour palette =======================
PRIMARY        = colors.HexColor("#667eea")
PRIMARY_DARK   = colors.HexColor("#5a67d8")
ACCENT         = colors.HexColor("#764ba2")
SUCCESS        = colors.HexColor("#28a745")
WARNING        = colors.HexColor("#ffc107")
DANGER         = colors.HexColor("#dc3545")
LIGHT_BG       = colors.HexColor("#f8f9fa")
INFO_BG        = colors.HexColor("#e8f4fd")
WARN_BG        = colors.HexColor("#fff8e1")
BORDER         = colors.HexColor("#dee2e6")
TEXT_DARK      = colors.HexColor("#212529")
TEXT_MUTED     = colors.HexColor("#6c757d")

PAGE_W, PAGE_H = A4
LEFT_MARGIN    = 18 * mm
RIGHT_MARGIN   = 18 * mm
CONTENT_W      = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "rehab-logo.png")

# Score threshold below which we recommend an in-person center visit
CENTER_VISIT_SCORE_THRESHOLD = 20.0  # out of 50


# ====================== helpers =======================
def _fmt_duration(seconds):
    if seconds is None:
        return "--"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _score_colour(score, max_score=50.0):
    pct = (score / max_score * 100) if max_score else 0
    if pct >= 70:
        return SUCCESS
    if pct >= 40:
        return WARNING
    return DANGER


def _perc_colour(pct):
    if pct >= 100:
        return SUCCESS
    if pct >= 50:
        return WARNING
    return DANGER


def _field(row, key, default=None):
    """Read a value from either a dict or sqlite3.Row."""
    if hasattr(row, '__getitem__'):
        try:
            return row[key]
        except (KeyError, IndexError):
            return default
    return getattr(row, key, default)


# ====================== Groq LLM calls =======================
def _get_groq_client():
    if not _GROQ_AVAILABLE:
        return None
    api_key = os.getenv(
        "GROQ_API_KEY",
        "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",
    )
    if not api_key:
        return None
    try:
        return _Groq(api_key=api_key.strip())
    except Exception:
        return None


def _llm_chat(client, system, user, temperature=0.4, max_tokens=500):
    """Single Groq chat completion. Returns raw text or empty string."""
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[REPORT LLM] Error: {e}")
        return ""


def _generate_exercise_feedback(client, exercise_name, avg_score, correct_pct,
                                max_reps, max_sets, program):
    """Ask LLM for per-exercise improvement tips."""
    system = (
        "You are a physiotherapy rehabilitation expert writing a concise "
        "medical report section. Be professional, clear, and actionable."
    )
    user = (
        "Write a SHORT paragraph (3-4 sentences max) evaluating the patient's "
        "performance on the exercise below.\n"
        "Include:\n"
        "1) How well the patient performed (based on average score and correct-form percentage).\n"
        "2) Specific areas of improvement or what to focus on next session.\n"
        "3) One encouraging note if performance was decent (correct%% > 50).\n\n"
        f"Exercise: {exercise_name}\n"
        f"Program: {program}\n"
        f"Average Score: {avg_score:.1f} / 50\n"
        f"Correct Form %%: {correct_pct:.0f}%%\n"
        f"Reps Completed: {max_reps}\n"
        f"Sets Completed: {max_sets}\n\n"
        "Write ONLY the paragraph. No heading, no bullet list, no markdown."
    )
    return _llm_chat(client, system, user, temperature=0.35, max_tokens=250)


def _generate_session_summary(client, patient_name, condition, quality_score,
                              completed_perc, pain_before, pain_after,
                              effort, duration_str, exercise_summaries,
                              needs_center_visit):
    """Ask LLM for an overall session summary with optional center-visit rec."""
    system = (
        "You are a senior physiotherapy consultant writing a final summary "
        "for a rehabilitation session report. Be concise, professional, "
        "and medically appropriate."
    )

    ex_lines = ""
    for es in exercise_summaries:
        ex_lines += (
            f"  - {es['name']}: avg_score={es['avg_score']:.1f}/50, "
            f"correct={es['correct_pct']:.0f}%%, reps={es['max_reps']}, sets={es['max_sets']}\n"
        )

    if needs_center_visit:
        center_instruction = (
            "\nIMPORTANT: The aggregate quality score is BELOW the safe threshold "
            f"({CENTER_VISIT_SCORE_THRESHOLD}/50). You MUST recommend that the patient "
            "books an in-person appointment at the rehabilitation center for supervised "
            "training before continuing home exercises. Phrase this politely but firmly."
        )
    else:
        center_instruction = (
            "\nThe score is above the safe threshold - the patient can safely continue "
            "home-based rehabilitation. Mention this positively."
        )

    user = (
        "Write a CONCISE final summary (5-7 sentences) for this rehabilitation session report.\n\n"
        f"Patient: {patient_name}\n"
        f"Condition: {condition}\n"
        f"Overall Quality Score: {quality_score:.1f} / 50\n"
        f"Session Completion: {completed_perc:.0f}%%\n"
        f"Pain Level: {pain_before} (before) -> {pain_after} (after)\n"
        f"Effort Level: {effort}/10\n"
        f"Duration: {duration_str}\n\n"
        f"Exercises performed:\n{ex_lines}"
        f"{center_instruction}\n\n"
        "Include:\n"
        "1) Overall assessment of the session.\n"
        "2) Key strengths observed.\n"
        "3) Primary areas needing improvement.\n"
        "4) Whether the patient should continue home exercises or visit the center.\n"
        "5) Brief next-steps suggestion.\n\n"
        "Write ONLY the summary paragraph. No heading, no bullet list, no markdown."
    )
    return _llm_chat(client, system, user, temperature=0.35, max_tokens=400)


# ====================== page chrome =======================
def _header_footer(canvas, doc):
    """Draw header bar + footer on every page."""
    canvas.saveState()

    bar_h = 22 * mm
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(PAGE_W * 0.6, PAGE_H - bar_h, PAGE_W * 0.4, bar_h, fill=1, stroke=0)

    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(
                LOGO_PATH, LEFT_MARGIN, PAGE_H - bar_h + 3 * mm,
                width=16 * mm, height=16 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(LEFT_MARGIN + 20 * mm, PAGE_H - bar_h + 7 * mm,
                      "Home Rehab Coach")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_MARGIN + 20 * mm, PAGE_H - bar_h + 2.5 * mm,
                      "Rehabilitation Session Report")
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - bar_h + 4 * mm,
                           datetime.now().strftime("Generated %d %b %Y, %H:%M"))

    # footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, 14 * mm, PAGE_W - RIGHT_MARGIN, 14 * mm)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(LEFT_MARGIN, 10 * mm,
                      "Confidential - For Medical Use Only")
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, 10 * mm,
                           f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


# ====================== public API =======================
def generate_session_report(
    patient_name,
    patient_condition,
    session_data,
    exercises,
    frames,
    overall_duration=None,
):
    """Return the PDF as in-memory bytes.

    Parameters
    ----------
    patient_name, patient_condition : str
    session_data : dict-like  (quality_score, completed_perc, pain_before,
                               pain_after, effort_level, started_at, completed_at)
    exercises : list[dict]  (exercise_name, quality_score, completion_perc,
                             sets_required, sets_completed, duration_seconds)
    frames : list[dict-like]  (timestamp, exercise_name, score, status,
                               rep_count, set_count, program)
    overall_duration : int or None  (seconds)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LEFT_MARGIN, rightMargin=RIGHT_MARGIN,
        topMargin=30 * mm, bottomMargin=22 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"],
        textColor=PRIMARY_DARK, fontSize=13,
        spaceAfter=4 * mm, spaceBefore=6 * mm))
    styles.add(ParagraphStyle(
        "CenterSmall", parent=styles["Normal"],
        alignment=TA_CENTER, textColor=TEXT_MUTED, fontSize=8))
    styles.add(ParagraphStyle(
        "LLMBody", parent=styles["Normal"],
        textColor=TEXT_DARK, fontSize=9, leading=13,
        spaceBefore=2 * mm, spaceAfter=2 * mm,
        leftIndent=6, rightIndent=6))
    styles.add(ParagraphStyle(
        "LLMExTitle", parent=styles["Normal"],
        textColor=PRIMARY_DARK, fontSize=10,
        fontName="Helvetica-Bold", spaceBefore=4 * mm, spaceAfter=1 * mm))
    styles.add(ParagraphStyle(
        "SummaryBox", parent=styles["Normal"],
        textColor=TEXT_DARK, fontSize=9.5, leading=14,
        spaceBefore=3 * mm, spaceAfter=2 * mm,
        leftIndent=8, rightIndent=8))

    story = []

    # --- Extract session data ---
    quality    = float(session_data.get('quality_score', 0) or 0)
    comp_perc  = float(session_data.get('completed_perc', 0) or 0)
    pain_b     = int(session_data.get('pain_before', 0) or 0)
    pain_a     = int(session_data.get('pain_after', 0) or 0)
    effort_val = int(session_data.get('effort_level', 5) or 5)
    started_at = session_data.get('started_at', '') or ''

    # --- Build set of user-selected exercise names ---
    selected_exercises = set()
    for ex in (exercises or []):
        ename = ex.get("exercise_name", "")
        if ename:
            selected_exercises.add(ename)

    # --- Aggregate frame-level stats per exercise (only selected) ---
    ex_agg = {}
    def _new_agg():
        return dict(total_score=0, count=0, correct=0, wrong=0,
                    max_rep=0, max_set=0, program="general")

    for f in (frames or []):
        ename  = _field(f, 'exercise_name', '')
        if not ename or ename in ("no_pose", "idle", "error", "none", "no_frame"):
            continue
        # Skip exercises the user did not select
        if selected_exercises and ename not in selected_exercises:
            continue
        score  = float(_field(f, 'score', 0))
        status = _field(f, 'status', '')
        rep    = int(_field(f, 'rep_count', 0))
        st     = int(_field(f, 'set_count', 1))
        prog   = _field(f, 'program', 'general')

        if ename not in ex_agg:
            ex_agg[ename] = _new_agg()
        agg = ex_agg[ename]
        agg["total_score"] += score
        agg["count"] += 1
        if status == "CORRECT":
            agg["correct"] += 1
        elif status == "WRONG":
            agg["wrong"] += 1
        agg["max_rep"] = max(agg["max_rep"], rep)
        agg["max_set"] = max(agg["max_set"], st)
        agg["program"] = prog

    # --- Call Groq LLM for feedback (done BEFORE building PDF) ---
    groq_client = _get_groq_client()

    exercise_feedbacks = {}   # exercise_name -> feedback text
    exercise_summary_rows = []

    if groq_client and ex_agg:
        print("[REPORT] Generating LLM feedback for exercises...")
        for ename, agg in ex_agg.items():
            avg_s = agg["total_score"] / agg["count"] if agg["count"] else 0
            cpct  = agg["correct"] / agg["count"] * 100 if agg["count"] else 0
            prog_label = "Low Back Pain" if agg["program"] == "low_back_pain" else "General"

            fb = _generate_exercise_feedback(
                groq_client,
                exercise_name=ename.replace("_", " ").title(),
                avg_score=avg_s, correct_pct=cpct,
                max_reps=agg["max_rep"], max_sets=agg["max_set"],
                program=prog_label,
            )
            exercise_feedbacks[ename] = fb
            exercise_summary_rows.append(dict(
                name=ename.replace("_", " ").title(),
                avg_score=avg_s, correct_pct=cpct,
                max_reps=agg["max_rep"], max_sets=agg["max_set"],
            ))

        # Overall summary
        needs_center = quality < CENTER_VISIT_SCORE_THRESHOLD
        print("[REPORT] Generating LLM session summary...")
        session_summary_text = _generate_session_summary(
            groq_client,
            patient_name=patient_name or "Patient",
            condition=patient_condition or "General",
            quality_score=quality, completed_perc=comp_perc,
            pain_before=pain_b, pain_after=pain_a,
            effort=effort_val,
            duration_str=_fmt_duration(overall_duration),
            exercise_summaries=exercise_summary_rows,
            needs_center_visit=needs_center,
        )
        print("[REPORT] LLM generation complete.")
    else:
        session_summary_text = ""

    # =================================================================
    # BUILD PDF STORY
    # =================================================================

    # --- patient info banner ---
    info_data = [
        ["Patient",      patient_name or "N/A"],
        ["Condition",    patient_condition or "General Rehabilitation"],
        ["Session Date", started_at[:16].replace("T", "  ") if started_at else "N/A"],
        ["Duration",     _fmt_duration(overall_duration)],
    ]
    info_table = Table(info_data, colWidths=[35 * mm, CONTENT_W - 35 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (0, 0), (0, -1), PRIMARY_DARK),
        ("TEXTCOLOR",     (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, BORDER),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # --- stat cards ---
    story.append(Paragraph("Overall Performance", styles["SectionTitle"]))
    card_w = CONTENT_W / 4 - 2 * mm

    def _card(label, value, colour=TEXT_DARK):
        return [
            Paragraph(
                '<font color="%s" size="18"><b>%s</b></font>' % (colour.hexval(), value),
                styles["Normal"]),
            Paragraph(
                '<font color="%s" size="8">%s</font>' % (TEXT_MUTED.hexval(), label),
                styles["Normal"]),
        ]

    cards_data = [
        _card("Quality Score", "%.1f/50" % quality, _score_colour(quality)),
        _card("Completion",    "%.0f%%" % comp_perc,  _perc_colour(comp_perc)),
        _card("Pain Change",   "%d -> %d" % (pain_b, pain_a),
              SUCCESS if pain_a <= pain_b else DANGER),
        _card("Effort",        "%d/10" % effort_val, TEXT_DARK),
    ]
    card_tables = []
    for card in cards_data:
        t = Table([[card[0]], [card[1]]], colWidths=[card_w])
        t.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_BG),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        card_tables.append(t)

    row_table = Table([card_tables], colWidths=[card_w + 2 * mm] * 4)
    row_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(row_table)
    story.append(Spacer(1, 6 * mm))

    # --- exercise breakdown table ---
    if exercises:
        story.append(Paragraph("Exercise Breakdown", styles["SectionTitle"]))
        header = ["Exercise", "Quality", "Completion", "Sets (Done/Target)", "Time"]
        rows = [header]
        for ex in exercises:
            ex_name   = ex.get("exercise_name", "")
            ex_q      = float(ex.get("quality_score", 0) or 0)
            ex_perc   = float(ex.get("completion_perc", 0) or 0)
            sets_req  = ex.get("sets_required") or {}
            sets_comp = ex.get("sets_completed") or {}
            t_req  = sum(int(v) for v in sets_req.values()) if isinstance(sets_req, dict) else 0
            t_comp = sum(int(v) for v in sets_comp.values()) if isinstance(sets_comp, dict) else 0
            dur = ex.get("duration_seconds")
            pc = _perc_colour(ex_perc)
            rows.append([
                ex_name,
                "%.1f" % ex_q,
                Paragraph(
                    '<font color="%s"><b>%.0f%%</b></font>' % (pc.hexval(), ex_perc),
                    styles["Normal"]),
                "%d / %d" % (t_comp, t_req),
                _fmt_duration(dur),
            ])
        cw = [CONTENT_W * f for f in (0.28, 0.14, 0.18, 0.22, 0.18)]
        ex_table = Table(rows, colWidths=cw, repeatRows=1)
        ex_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0), 9),
            ("FONTSIZE",       (0, 1), (-1, -1), 9),
            ("ALIGN",          (1, 0), (-1, -1), "CENTER"),
            ("ALIGN",          (0, 0), (0, -1), "LEFT"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
            ("LEFTPADDING",    (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ]))
        story.append(ex_table)
        story.append(Spacer(1, 6 * mm))

    # --- LLM per-exercise feedback ---
    if exercise_feedbacks:
        story.append(Paragraph(
            "Exercise Performance &amp; Improvement Tips",
            styles["SectionTitle"]))
        story.append(Paragraph(
            "<i>AI-generated analysis based on session data. "
            "Please consult your physiotherapist for personalised guidance.</i>",
            ParagraphStyle("LLMDisclaimer", parent=styles["Normal"],
                           textColor=TEXT_MUTED, fontSize=7.5,
                           spaceAfter=3 * mm, fontName="Helvetica-Oblique"),
        ))

        for ename, fb_text in exercise_feedbacks.items():
            if not fb_text:
                continue
            display_name = ename.replace("_", " ").title()
            agg = ex_agg.get(ename, {})
            avg_s = agg.get("total_score", 0) / max(agg.get("count", 1), 1)
            cpct  = agg.get("correct", 0) / max(agg.get("count", 1), 1) * 100

            sc = _score_colour(avg_s)
            story.append(Paragraph(
                '<font color="%s">&#9679;</font> %s  '
                '<font size="8" color="%s">(avg %.1f/50 | %.0f%% correct)</font>'
                % (sc.hexval(), display_name, TEXT_MUTED.hexval(), avg_s, cpct),
                styles["LLMExTitle"],
            ))

            fb_table = Table(
                [[Paragraph(fb_text, styles["LLMBody"])]],
                colWidths=[CONTENT_W - 4 * mm],
            )
            fb_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), INFO_BG),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ("LEFTPADDING",   (0, 0), (-1, -1), 8),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(fb_table)

        story.append(Spacer(1, 4 * mm))

    # --- score timeline chart ---
    if frames and len(frames) > 1:
        story.append(Paragraph("Score Timeline", styles["SectionTitle"]))
        story.append(Paragraph(
            "Frame-by-frame quality score over the session.",
            ParagraphStyle("TDesc", parent=styles["Normal"],
                           textColor=TEXT_MUTED, fontSize=8, spaceAfter=3 * mm)))

        ex_frames = defaultdict(list)
        for i, f in enumerate(frames):
            en = _field(f, 'exercise_name', '')
            sc = float(_field(f, 'score', 0))
            # Only chart selected exercises
            if selected_exercises and en not in selected_exercises:
                continue
            ex_frames[en].append((i, sc))

        drawing = Drawing(CONTENT_W, 120)
        plot = LinePlot()
        plot.x = 40
        plot.y = 20
        plot.width = float(CONTENT_W) - 60
        plot.height = 85

        line_colors = [PRIMARY, ACCENT, SUCCESS, WARNING, DANGER,
                       colors.HexColor("#17a2b8"), colors.HexColor("#fd7e14")]
        data_sets = []
        legend_labels = []
        for idx, (en, pts) in enumerate(ex_frames.items()):
            if not en or en in ("no_pose", "idle", "error", "none", "no_frame"):
                continue
            if len(pts) > 200:
                step = max(1, len(pts) // 200)
                pts = pts[::step]
            data_sets.append(pts)
            legend_labels.append(en.replace("_", " ").title())

        if data_sets:
            plot.data = data_sets
            for i in range(len(data_sets)):
                plot.lines[i].strokeColor = line_colors[i % len(line_colors)]
                plot.lines[i].strokeWidth = 1.2
            plot.xValueAxis.valueMin = 0
            plot.xValueAxis.labels.fontSize = 7
            plot.xValueAxis.labels.fillColor = TEXT_MUTED
            plot.yValueAxis.valueMin = 0
            plot.yValueAxis.valueMax = 50
            plot.yValueAxis.valueStep = 10
            plot.yValueAxis.labels.fontSize = 7
            plot.yValueAxis.labels.fillColor = TEXT_MUTED
            drawing.add(plot)

            legend_parts = []
            for i, lbl in enumerate(legend_labels):
                c = line_colors[i % len(line_colors)]
                legend_parts.append(
                    '<font color="%s">&#9632;</font> %s' % (c.hexval(), lbl)
                )
            story.append(drawing)
            story.append(Paragraph(
                "  &nbsp;&nbsp;".join(legend_parts),
                ParagraphStyle("Legend", parent=styles["Normal"],
                               alignment=TA_CENTER, fontSize=8, spaceAfter=4 * mm)))
        else:
            story.append(Paragraph("<i>No scoreable frames recorded.</i>",
                                   styles["CenterSmall"]))
        story.append(Spacer(1, 4 * mm))

    # --- detailed performance metrics table ---
    if ex_agg:
        story.append(Paragraph("Detailed Performance Metrics", styles["SectionTitle"]))
        header = ["Exercise", "Program", "Avg Score", "Correct %",
                  "Frames", "Reps", "Sets"]
        rows = [header]
        for ename, agg in ex_agg.items():
            avg_s = agg["total_score"] / agg["count"] if agg["count"] else 0
            cpct  = agg["correct"] / agg["count"] * 100 if agg["count"] else 0
            plbl  = "Low Back Pain" if agg["program"] == "low_back_pain" else "General"
            pc = _perc_colour(cpct)
            rows.append([
                ename.replace("_", " ").title(),
                plbl,
                "%.1f" % avg_s,
                Paragraph(
                    '<font color="%s"><b>%.0f%%</b></font>' % (pc.hexval(), cpct),
                    styles["Normal"]),
                str(agg["count"]),
                str(agg["max_rep"]),
                str(agg["max_set"]),
            ])
        cw = [CONTENT_W * f for f in (0.22, 0.16, 0.12, 0.14, 0.12, 0.10, 0.10)]
        pt = Table(rows, colWidths=cw, repeatRows=1)
        pt.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), PRIMARY_DARK),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("ALIGN",          (1, 0), (-1, -1), "CENTER"),
            ("ALIGN",          (0, 0), (0, -1), "LEFT"),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("GRID",           (0, 0), (-1, -1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("TOPPADDING",     (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        story.append(pt)
        story.append(Spacer(1, 6 * mm))

    # --- LLM session summary ---
    story.append(Paragraph("Session Summary &amp; Recommendations",
                           styles["SectionTitle"]))

    if session_summary_text:
        bg = WARN_BG if quality < CENTER_VISIT_SCORE_THRESHOLD else INFO_BG
        sum_table = Table(
            [[Paragraph(session_summary_text, styles["SummaryBox"])]],
            colWidths=[CONTENT_W - 4 * mm],
        )
        sum_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, -1), bg),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("LEFTPADDING",    (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
            ("TOPPADDING",     (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(sum_table)
    else:
        # Fallback when LLM is unavailable
        fallback = (
            "Session quality score: <b>%.1f/50</b>. "
            "Completion: <b>%.0f%%</b>. " % (quality, comp_perc)
        )
        if quality < CENTER_VISIT_SCORE_THRESHOLD:
            fallback += (
                "<br/><br/><b>Note:</b> The aggregate quality score is below "
                "the recommended threshold (%.0f/50). "
                "We strongly recommend booking an in-person session at the "
                "rehabilitation center for supervised guidance before continuing "
                "home-based exercises." % CENTER_VISIT_SCORE_THRESHOLD
            )
        else:
            fallback += (
                "The patient demonstrates adequate form for home-based "
                "rehabilitation. Continue the current programme."
            )
        story.append(Paragraph(fallback, styles["SummaryBox"]))

    # Center-visit alert banner (always shown if below threshold)
    if quality < CENTER_VISIT_SCORE_THRESHOLD:
        story.append(Spacer(1, 3 * mm))
        alert_table = Table(
            [[Paragraph(
                '<font size="11">&#9888;</font> '
                '<b>Recommendation:</b> Please book an appointment at your nearest '
                'rehabilitation center for supervised exercise training.',
                ParagraphStyle("AlertInner", parent=styles["Normal"],
                               textColor=DANGER, fontSize=9.5,
                               alignment=TA_CENTER),
            )]],
            colWidths=[CONTENT_W - 4 * mm],
        )
        alert_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, -1), colors.HexColor("#fde8e8")),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("TOPPADDING",     (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
            ("LEFTPADDING",    (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
        ]))
        story.append(alert_table)

    # --- disclaimer ---
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "This report is auto-generated by <b>Home Rehab Coach</b> and is intended "
        "as a supplementary tool for clinical decision-making. It does not replace "
        "professional medical assessment. Please consult your physiotherapist or "
        "physician for clinical interpretation.",
        ParagraphStyle("Disclaimer", parent=styles["Normal"],
                       textColor=TEXT_MUTED, fontSize=7, alignment=TA_CENTER),
    ))

    # --- build ---
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
