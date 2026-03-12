"""
report_generator.py  –  Professional PDF rehabilitation report with Groq LLM insights.

Sections:
  1. Cover header with branding
  2. Patient information card
  3. Overall performance dashboard (stat cards)
  4. Session goals vs achievements
  5. Exercise breakdown table
  6. Per-exercise AI analysis & improvement tips  (Groq LLM)
  7. Score timeline chart
  8. Detailed performance metrics
  9. AI session summary & recommendations          (Groq LLM)
 10. Next steps & action items
 11. Medical disclaimer
"""

import io, os, math
from datetime import datetime
from collections import defaultdict, OrderedDict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
from reportlab.graphics.charts.lineplots import LinePlot

# ── Groq LLM ────────────────────────────────────────────────────────────
try:
    from groq import Groq as _Groq
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

# ══════════════════════  COLOUR PALETTE  ══════════════════════════════════
PRIMARY         = colors.HexColor("#667eea")
PRIMARY_DARK    = colors.HexColor("#5a67d8")
PRIMARY_LIGHT   = colors.HexColor("#b3c4ff")
ACCENT          = colors.HexColor("#764ba2")
SUCCESS         = colors.HexColor("#28a745")
SUCCESS_LIGHT   = colors.HexColor("#d4edda")
WARNING         = colors.HexColor("#e67e22")
WARNING_LIGHT   = colors.HexColor("#fff3cd")
DANGER          = colors.HexColor("#dc3545")
DANGER_LIGHT    = colors.HexColor("#f8d7da")
NEUTRAL         = colors.HexColor("#6c757d")
LIGHT_BG        = colors.HexColor("#f8f9fa")
INFO_BG         = colors.HexColor("#e8f4fd")
INFO_BG2        = colors.HexColor("#dbeafe")
WARM_BG         = colors.HexColor("#fef9e7")
BORDER          = colors.HexColor("#dee2e6")
BORDER_LIGHT    = colors.HexColor("#e9ecef")
TEXT_DARK       = colors.HexColor("#212529")
TEXT_BODY       = colors.HexColor("#343a40")
TEXT_MUTED      = colors.HexColor("#6c757d")
WHITE           = colors.white

PAGE_W, PAGE_H  = A4
LEFT_M          = 18 * mm
RIGHT_M         = 18 * mm
CW              = PAGE_W - LEFT_M - RIGHT_M         # content width

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "rehab-logo.png")

# ── thresholds ──
CENTER_VISIT_SCORE_THRESHOLD = 20.0   # out of 50


# ═══════════════════════  HELPERS  ════════════════════════════════════════
def _dur(seconds):
    if seconds is None: return "--"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"

def _norm(name):
    """Normalise an exercise name for comparison (lower, strip, collapse spaces)."""
    return " ".join((name or "").lower().replace("_", " ").split())

def _title(name):
    return (name or "").replace("_", " ").strip().title()

def _score_col(score, mx=50.0):
    p = (score / mx * 100) if mx else 0
    if p >= 70: return SUCCESS
    if p >= 40: return WARNING
    return DANGER

def _pct_col(pct):
    if pct >= 70: return SUCCESS
    if pct >= 40: return WARNING
    return DANGER

def _score_label(score, mx=50.0):
    p = (score / mx * 100) if mx else 0
    if p >= 80: return "Excellent"
    if p >= 60: return "Good"
    if p >= 40: return "Fair"
    if p >= 20: return "Needs Improvement"
    return "Poor"

def _field(row, key, default=None):
    if hasattr(row, '__getitem__'):
        try: return row[key]
        except (KeyError, IndexError): return default
    return getattr(row, key, default)


# ═══════════════════════  GROQ LLM CALLS  ════════════════════════════════
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

def _llm(client, system, user, temp=0.4, tokens=500):
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role":"system","content":system},
                      {"role":"user","content":user}],
            temperature=temp, max_tokens=tokens,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[REPORT LLM] {e}")
        return ""

def _llm_exercise_feedback(client, name, avg, cpct, reps, sets, prog):
    sys = (
        "You are a senior physiotherapy rehabilitation specialist writing a "
        "medical report. Be professional, clear, specific, and actionable."
    )
    usr = (
        f"Write a detailed paragraph (5-7 sentences) evaluating the patient's "
        f"performance on the exercise below. Include:\n"
        f"1) Overall performance assessment based on score & correct-form percentage.\n"
        f"2) What the patient did well (strengths).\n"
        f"3) Specific areas of improvement with actionable tips.\n"
        f"4) Recommended focus areas or modifications for next session.\n"
        f"5) An encouraging closing remark if appropriate.\n\n"
        f"Exercise: {name}\nProgram: {prog}\n"
        f"Average Score: {avg:.1f}/50\nCorrect Form: {cpct:.0f}%\n"
        f"Reps Completed: {reps}\nSets Completed: {sets}\n\n"
        f"Write ONLY the paragraph. No heading, no bullets, no markdown."
    )
    return _llm(client, sys, usr, temp=0.35, tokens=350)

def _llm_session_summary(client, pname, condition, quality, comp, pain_b, pain_a,
                         effort, dur_str, ex_rows, need_center):
    sys = (
        "You are a senior physiotherapy consultant writing a comprehensive "
        "final summary for a medical rehabilitation session report."
    )
    ex_lines = "\n".join(
        f"  - {r['name']}: avg={r['avg']:.1f}/50, correct={r['cpct']:.0f}%, "
        f"reps={r['reps']}, sets={r['sets']}"
        for r in ex_rows
    )
    center = (
        f"\nIMPORTANT: Quality score is BELOW the safe threshold ({CENTER_VISIT_SCORE_THRESHOLD}/50). "
        "You MUST recommend the patient book an in-person appointment at the rehab center "
        "for supervised training before continuing home exercises. Phrase politely but firmly."
        if need_center else
        "\nThe score is above the safe threshold. Affirm the patient can safely continue "
        "home-based rehabilitation."
    )
    usr = (
        f"Write a COMPREHENSIVE session summary (8-10 sentences).\n\n"
        f"Patient: {pname}\nCondition: {condition}\n"
        f"Quality Score: {quality:.1f}/50\nCompletion: {comp:.0f}%\n"
        f"Pain: {pain_b} (before) -> {pain_a} (after)\n"
        f"Effort: {effort}/10\nDuration: {dur_str}\n\n"
        f"Exercises:\n{ex_lines}\n{center}\n\n"
        f"Include:\n"
        f"1) Overall session assessment\n"
        f"2) Key strengths observed\n"
        f"3) Primary improvement areas\n"
        f"4) Pain management observations\n"
        f"5) Whether to continue home exercises or visit center\n"
        f"6) Specific next-steps\n\n"
        f"Write ONLY the paragraph. No heading, no bullets, no markdown."
    )
    return _llm(client, sys, usr, temp=0.35, tokens=500)

def _llm_next_steps(client, pname, quality, ex_rows, need_center):
    sys = "You are a physiotherapy consultant providing actionable next steps."
    ex_lines = "\n".join(f"  - {r['name']}: avg={r['avg']:.1f}/50" for r in ex_rows)
    usr = (
        f"Based on the session data below, write exactly 4-5 numbered action items "
        f"the patient should follow before the next session. Be specific and practical.\n\n"
        f"Patient: {pname}\nQuality: {quality:.1f}/50\n"
        f"Exercises:\n{ex_lines}\n"
        f"{'Must visit center for supervised session.' if need_center else ''}\n\n"
        f"Format: Return ONLY numbered lines like:\n"
        f"1. ...\n2. ...\netc.\nNo extra text."
    )
    return _llm(client, sys, usr, temp=0.3, tokens=300)


# ═══════════════════════  PAGE HEADER / FOOTER  ══════════════════════════
def _chrome(canvas, doc):
    canvas.saveState()
    bh = 22 * mm
    # gradient bar
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H - bh, PAGE_W, bh, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(PAGE_W * 0.55, PAGE_H - bh, PAGE_W * 0.45, bh, fill=1, stroke=0)
    # logo
    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(LOGO_PATH, LEFT_M, PAGE_H - bh + 3*mm,
                             16*mm, 16*mm, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    # titles
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(LEFT_M + 20*mm, PAGE_H - bh + 7*mm, "Home Rehab Coach")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_M + 20*mm, PAGE_H - bh + 2.5*mm,
                      "Rehabilitation Session Report")
    canvas.drawRightString(PAGE_W - RIGHT_M, PAGE_H - bh + 7.5*mm,
                           datetime.now().strftime("Generated %d %b %Y, %H:%M"))
    canvas.setFont("Helvetica-Oblique", 7.5)
    canvas.drawRightString(PAGE_W - RIGHT_M, PAGE_H - bh + 3*mm,
                           "Confidential - For Medical Use Only")
    # footer line
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_M, 14*mm, PAGE_W - RIGHT_M, 14*mm)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(LEFT_M, 10*mm,
                      "Home Rehab Coach  |  AI-Powered Rehabilitation Report")
    canvas.drawRightString(PAGE_W - RIGHT_M, 10*mm,
                           f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


# ═══════════════════════  BUILDING BLOCKS  ════════════════════════════════
def _section(title, styles, icon=None):
    """Section heading. Icons are plain Helvetica-safe characters."""
    return Paragraph(title, styles["SectionTitle"])

def _coloured_box(content_para, bg_colour, border_colour=None, col_widths=None):
    """Wrap a Paragraph in a rounded-corner coloured box."""
    w = col_widths or [CW - 4*mm]
    t = Table([[content_para]], colWidths=w)
    style_cmds = [
        ("BACKGROUND",     (0,0),(-1,-1), bg_colour),
        ("ROUNDEDCORNERS", [5,5,5,5]),
        ("LEFTPADDING",    (0,0),(-1,-1), 10),
        ("RIGHTPADDING",   (0,0),(-1,-1), 10),
        ("TOPPADDING",     (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",  (0,0),(-1,-1), 8),
    ]
    if border_colour:
        style_cmds.append(("BOX", (0,0),(-1,-1), 0.8, border_colour))
    t.setStyle(TableStyle(style_cmds))
    return t


# ═══════════════════════  PUBLIC API  ════════════════════════════════════
def generate_session_report(
    patient_name,
    patient_condition,
    session_data,
    exercises,
    frames,
    overall_duration=None,
):
    """Return PDF as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LEFT_M, rightMargin=RIGHT_M,
        topMargin=30*mm, bottomMargin=22*mm,
    )

    # ── styles ──────────────────────────────────────────────────────────
    S = getSampleStyleSheet()
    S.add(ParagraphStyle("SectionTitle", parent=S["Heading2"],
                         textColor=PRIMARY_DARK, fontSize=13, fontName="Helvetica-Bold",
                         spaceAfter=5*mm, spaceBefore=8*mm,
                         borderWidth=0, borderColor=PRIMARY,
                         borderPadding=(0, 0, 2, 0)))
    S.add(ParagraphStyle("SubHead", parent=S["Normal"],
                         textColor=TEXT_DARK, fontSize=11, fontName="Helvetica-Bold",
                         spaceAfter=2*mm, spaceBefore=4*mm))
    S.add(ParagraphStyle("Body", parent=S["Normal"],
                         textColor=TEXT_BODY, fontSize=9.5, leading=14,
                         alignment=TA_JUSTIFY))
    S.add(ParagraphStyle("BodySmall", parent=S["Normal"],
                         textColor=TEXT_BODY, fontSize=8.5, leading=12))
    S.add(ParagraphStyle("CenterMuted", parent=S["Normal"],
                         alignment=TA_CENTER, textColor=TEXT_MUTED, fontSize=7.5))
    S.add(ParagraphStyle("LLMBody", parent=S["Normal"],
                         textColor=TEXT_BODY, fontSize=9.5, leading=14,
                         leftIndent=6, rightIndent=6, alignment=TA_JUSTIFY))
    S.add(ParagraphStyle("ExTitle", parent=S["Normal"],
                         textColor=PRIMARY_DARK, fontSize=11,
                         fontName="Helvetica-Bold", spaceBefore=5*mm, spaceAfter=1.5*mm))
    S.add(ParagraphStyle("CardValue", parent=S["Normal"],
                         alignment=TA_CENTER, fontSize=18, fontName="Helvetica-Bold",
                         leading=22))
    S.add(ParagraphStyle("CardLabel", parent=S["Normal"],
                         alignment=TA_CENTER, textColor=TEXT_MUTED, fontSize=7.5,
                         leading=10))
    S.add(ParagraphStyle("AlertText", parent=S["Normal"],
                         textColor=DANGER, fontSize=10, alignment=TA_CENTER,
                         fontName="Helvetica-Bold"))
    S.add(ParagraphStyle("StepItem", parent=S["Normal"],
                         textColor=TEXT_BODY, fontSize=9.5, leading=14,
                         leftIndent=8, rightIndent=8))

    story = []

    # ── extract session data ────────────────────────────────────────────
    quality   = float(session_data.get('quality_score', 0) or 0)
    comp_perc = float(session_data.get('completed_perc', 0) or 0)
    pain_b    = int(session_data.get('pain_before', 0) or 0)
    pain_a    = int(session_data.get('pain_after', 0) or 0)
    effort    = int(session_data.get('effort_level', 5) or 5)
    started   = session_data.get('started_at', '') or ''
    needs_center = quality < CENTER_VISIT_SCORE_THRESHOLD

    # ── build normalised set of selected exercise names ────────────────
    selected_norm = set()
    for ex in (exercises or []):
        n = _norm(ex.get("exercise_name", ""))
        if n:
            selected_norm.add(n)

    # helper to check membership
    def _is_selected(name):
        return (not selected_norm) or _norm(name) in selected_norm

    # ── aggregate frame stats (only selected exercises) ────────────────
    SKIP = {"no_pose", "idle", "error", "none", "no_frame", "ideal", ""}
    ex_agg = OrderedDict()

    def _new():
        return dict(total=0, n=0, correct=0, wrong=0,
                    max_rep=0, max_set=0, prog="general")

    for f in (frames or []):
        en = _field(f, 'exercise_name', '')
        if _norm(en) in SKIP:
            continue
        if not _is_selected(en):
            continue
        sc  = float(_field(f, 'score', 0))
        st  = _field(f, 'status', '')
        rep = int(_field(f, 'rep_count', 0))
        se  = int(_field(f, 'set_count', 1))
        pr  = _field(f, 'program', 'general')
        key = _norm(en)
        if key not in ex_agg:
            ex_agg[key] = _new()
            ex_agg[key]["display"] = _title(en)
        a = ex_agg[key]
        a["total"] += sc;  a["n"] += 1
        if st == "CORRECT": a["correct"] += 1
        elif st == "WRONG": a["wrong"] += 1
        a["max_rep"] = max(a["max_rep"], rep)
        a["max_set"] = max(a["max_set"], se)
        a["prog"] = pr

    # ── call Groq LLM ──────────────────────────────────────────────────
    gclient = _get_groq_client()
    ex_fb = {}          # key -> feedback text
    ex_summary_rows = []
    session_summary_text = ""
    next_steps_text = ""

    if gclient and ex_agg:
        print("[REPORT] Generating LLM per-exercise feedback …")
        for key, a in ex_agg.items():
            avg = a["total"] / a["n"] if a["n"] else 0
            cp  = a["correct"] / a["n"] * 100 if a["n"] else 0
            plbl = "Low Back Pain" if a["prog"] == "low_back_pain" else "General"
            fb  = _llm_exercise_feedback(gclient, a["display"], avg, cp,
                                         a["max_rep"], a["max_set"], plbl)
            ex_fb[key] = fb
            ex_summary_rows.append(dict(name=a["display"], avg=avg, cpct=cp,
                                        reps=a["max_rep"], sets=a["max_set"]))

        print("[REPORT] Generating LLM session summary …")
        session_summary_text = _llm_session_summary(
            gclient, patient_name or "Patient", patient_condition or "General",
            quality, comp_perc, pain_b, pain_a, effort, _dur(overall_duration),
            ex_summary_rows, needs_center)

        print("[REPORT] Generating LLM next steps …")
        next_steps_text = _llm_next_steps(
            gclient, patient_name or "Patient", quality,
            ex_summary_rows, needs_center)
        print("[REPORT] LLM generation complete.")

    # ═══════════════════  BUILD PDF STORY  ═══════════════════════════════

    # ━━━━ 1. REPORT TITLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        '<b>Session Report</b>',
        ParagraphStyle("BigTitle", parent=S["Normal"],
                       textColor=PRIMARY_DARK, fontName="Helvetica-Bold",
                       fontSize=20, leading=24,
                       alignment=TA_LEFT, spaceBefore=0, spaceAfter=2*mm)))
    story.append(Paragraph(
        'Comprehensive AI-assisted rehabilitation analysis',
        ParagraphStyle("Sub", parent=S["Normal"],
                       textColor=TEXT_MUTED, fontSize=10, leading=13,
                       spaceAfter=4*mm)))
    story.append(HRFlowable(width="100%", thickness=1.2, color=PRIMARY,
                            spaceAfter=6*mm))

    # ━━━━ 2. PATIENT INFORMATION CARD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    story.append(_section("Patient Information", S))
    pi = [
        ["Patient Name",  patient_name or "N/A",
         "Condition",      patient_condition or "General Rehabilitation"],
        ["Session Date",   started[:16].replace("T","  ") if started else "N/A",
         "Duration",       _dur(overall_duration)],
        ["Program",        "Low Back Pain" if any(a["prog"]=="low_back_pain" for a in ex_agg.values()) else "General (Kimore)",
         "Exercises",      str(len(selected_norm) or len(ex_agg))],
    ]
    # Fix: use Kimore (correct spelling)
    # already set above
    pi_table = Table(pi, colWidths=[28*mm, CW/2 - 28*mm, 28*mm, CW/2 - 28*mm])
    pi_table.setStyle(TableStyle([
        ("FONTNAME",      (0,0),(0,-1), "Helvetica-Bold"),
        ("FONTNAME",      (2,0),(2,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("TEXTCOLOR",     (0,0),(0,-1), PRIMARY_DARK),
        ("TEXTCOLOR",     (2,0),(2,-1), PRIMARY_DARK),
        ("TEXTCOLOR",     (1,0),(1,-1), TEXT_BODY),
        ("TEXTCOLOR",     (3,0),(3,-1), TEXT_BODY),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("BACKGROUND",    (0,0),(-1,-1), LIGHT_BG),
        ("BOX",           (0,0),(-1,-1), 0.5, BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, BORDER_LIGHT),
        ("ROUNDEDCORNERS",[5,5,5,5]),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
    ]))
    story.append(pi_table)
    story.append(Spacer(1, 5*mm))

    # ━━━━ 3. OVERALL PERFORMANCE DASHBOARD ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    story.append(_section("Overall Performance Dashboard", S))

    def _card(label, value, colour, sublabel=""):
        val_p = Paragraph(
            '<font color="%s"><b>%s</b></font>' % (colour.hexval(), value),
            S["CardValue"])
        lbl_p = Paragraph(
            '<font color="%s">%s</font>' % (TEXT_MUTED.hexval(), label),
            S["CardLabel"])
        sub_p = Paragraph(
            '<font color="%s" size="7">%s</font>' % (colour.hexval(), sublabel),
            ParagraphStyle("csub", parent=S["Normal"], alignment=TA_CENTER, fontSize=7)
        ) if sublabel else Spacer(1, 0)
        return [val_p, lbl_p, sub_p]

    cw = CW / 5 - 1.5*mm
    cards = [
        _card("Quality Score", "%.1f/50" % quality,
              _score_col(quality), _score_label(quality)),
        _card("Completion", "%.0f%%" % comp_perc, _pct_col(comp_perc),
              "of session target"),
        _card("Pain Change", "%d to %d" % (pain_b, pain_a),
              SUCCESS if pain_a <= pain_b else DANGER,
              "Improved" if pain_a < pain_b else ("Stable" if pain_a == pain_b else "Increased")),
        _card("Effort", "%d/10" % effort, PRIMARY,
              "self-reported"),
        _card("Exercises", str(len(selected_norm) or len(ex_agg)),
              PRIMARY, "performed"),
    ]
    card_tabs = []
    for c in cards:
        t = Table([[c[0]],[c[1]],[c[2]]], colWidths=[cw])
        t.setStyle(TableStyle([
            ("ALIGN",          (0,0),(-1,-1),"CENTER"),
            ("VALIGN",         (0,0),(-1,-1),"MIDDLE"),
            ("TOPPADDING",     (0,0),(0,0), 10),
            ("BOTTOMPADDING",  (0,-1),(0,-1), 8),
            ("BACKGROUND",     (0,0),(-1,-1), LIGHT_BG),
            ("BOX",            (0,0),(-1,-1), 0.6, BORDER),
            ("ROUNDEDCORNERS", [4,4,4,4]),
        ]))
        card_tabs.append(t)
    row_t = Table([card_tabs], colWidths=[cw + 1.5*mm]*5)
    row_t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(row_t)
    story.append(Spacer(1, 5*mm))

    # ── performance rating bar ──
    rating = _score_label(quality)
    bar_col = _score_col(quality)
    rating_p = Paragraph(
        '<font size="10" color="%s"><b>Overall Rating: %s</b></font>'
        '&nbsp;&nbsp;&nbsp;'
        '<font color="%s" size="9">(%.1f / 50 – %s)</font>'
        % (bar_col.hexval(), rating, TEXT_MUTED.hexval(), quality,
           "above threshold" if not needs_center else "below recommended threshold"),
        ParagraphStyle("rp", parent=S["Normal"], spaceBefore=2*mm, spaceAfter=3*mm))
    story.append(_coloured_box(rating_p,
                               SUCCESS_LIGHT if not needs_center else DANGER_LIGHT,
                               border_colour=bar_col))
    story.append(Spacer(1, 4*mm))

    # ━━━━ 4. SESSION GOALS vs ACHIEVEMENTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if exercises:
        story.append(_section("Session Goals vs Achievements", S))
        ghdr = ["Exercise", "Target Sets", "Completed Sets", "Progress", "Status"]
        grows = [ghdr]
        for ex in exercises:
            en = ex.get("exercise_name", "")
            if not _is_selected(en) and selected_norm:
                continue
            import json as _json
            sr = ex.get("sets_required") or {}
            sc = ex.get("sets_completed") or {}
            if isinstance(sr, str):
                try: sr = _json.loads(sr)
                except: sr = {}
            if isinstance(sc, str):
                try: sc = _json.loads(sc)
                except: sc = {}
            tr = sum(int(v) for v in sr.values()) if isinstance(sr, dict) else 0
            tc = sum(int(v) for v in sc.values()) if isinstance(sc, dict) else 0
            pct = round(tc / tr * 100, 0) if tr > 0 else 0
            pc = _pct_col(pct)
            stat = "Complete" if pct >= 100 else ("Partial" if pct > 0 else "Missed")
            stat_col = SUCCESS if pct >= 100 else (WARNING if pct > 0 else DANGER)
            grows.append([
                _title(en),
                str(tr),
                str(tc),
                Paragraph('<font color="%s"><b>%.0f%%</b></font>' % (pc.hexval(), pct), S["Normal"]),
                Paragraph('<font color="%s">%s</font>' % (stat_col.hexval(), stat), S["Normal"]),
            ])
        gcw = [CW*f for f in (0.28, 0.16, 0.18, 0.16, 0.22)]
        gt = Table(grows, colWidths=gcw, repeatRows=1)
        gt.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,0), PRIMARY),
            ("TEXTCOLOR",      (0,0),(-1,0), WHITE),
            ("FONTNAME",       (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0),(-1,-1), 9),
            ("ALIGN",          (1,0),(-1,-1), "CENTER"),
            ("ALIGN",          (0,0),(0,-1), "LEFT"),
            ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
            ("GRID",           (0,0),(-1,-1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [WHITE, LIGHT_BG]),
            ("TOPPADDING",     (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 5),
            ("LEFTPADDING",    (0,0),(-1,-1), 6),
        ]))
        story.append(gt)
        story.append(Spacer(1, 5*mm))

    # ━━━━ 5. EXERCISE BREAKDOWN ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if exercises:
        story.append(_section("Exercise Breakdown", S))
        ehdr = ["Exercise", "Quality", "Completion", "Sets (Done/Target)", "Time"]
        erows = [ehdr]
        for ex in exercises:
            en = ex.get("exercise_name", "")
            if not _is_selected(en) and selected_norm:
                continue
            import json as _json
            eq = float(ex.get("quality_score", 0) or 0)
            sr = ex.get("sets_required") or {}
            sc_d = ex.get("sets_completed") or {}
            if isinstance(sr, str):
                try: sr = _json.loads(sr)
                except: sr = {}
            if isinstance(sc_d, str):
                try: sc_d = _json.loads(sc_d)
                except: sc_d = {}
            tr = sum(int(v) for v in sr.values()) if isinstance(sr, dict) else 0
            tc = sum(int(v) for v in sc_d.values()) if isinstance(sc_d, dict) else 0
            ep = round(tc / tr * 100, 1) if tr > 0 else 0
            dur = ex.get("duration_seconds")
            pc = _pct_col(ep)
            qc = _score_col(eq)
            erows.append([
                _title(en),
                Paragraph('<font color="%s"><b>%.1f</b></font>' % (qc.hexval(), eq), S["Normal"]),
                Paragraph('<font color="%s"><b>%.0f%%</b></font>' % (pc.hexval(), ep), S["Normal"]),
                "%d / %d" % (tc, tr),
                _dur(dur),
            ])
        ecw = [CW*f for f in (0.28, 0.14, 0.18, 0.22, 0.18)]
        et = Table(erows, colWidths=ecw, repeatRows=1)
        et.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,0), ACCENT),
            ("TEXTCOLOR",      (0,0),(-1,0), WHITE),
            ("FONTNAME",       (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0),(-1,-1), 9),
            ("ALIGN",          (1,0),(-1,-1), "CENTER"),
            ("ALIGN",          (0,0),(0,-1), "LEFT"),
            ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
            ("GRID",           (0,0),(-1,-1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [WHITE, LIGHT_BG]),
            ("TOPPADDING",     (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 5),
            ("LEFTPADDING",    (0,0),(-1,-1), 6),
        ]))
        story.append(et)
        story.append(Spacer(1, 5*mm))

    # ━━━━ 6. AI EXERCISE ANALYSIS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if ex_agg:
        story.append(_section("AI Exercise Analysis &amp; Improvement Tips", S))
        story.append(Paragraph(
            "<i>AI-generated analysis powered by Groq LLM. "
            "Consult your physiotherapist for personalised clinical guidance.</i>",
            ParagraphStyle("disc", parent=S["Normal"], textColor=TEXT_MUTED,
                           fontSize=7.5, spaceAfter=3*mm, fontName="Helvetica-Oblique")))

        for key, a in ex_agg.items():
            avg = a["total"] / a["n"] if a["n"] else 0
            cp  = a["correct"] / a["n"] * 100 if a["n"] else 0
            sc  = _score_col(avg)
            rating_lbl = _score_label(avg)

            # sub-header line
            story.append(Paragraph(
                '<font color="%s"><b>%s</b></font>'
                '&nbsp;&nbsp;&nbsp;'
                '<font size="8" color="%s">'
                'Avg %.1f/50 &nbsp;|&nbsp; %.0f%% correct &nbsp;|&nbsp; '
                '%d reps &nbsp;|&nbsp; %d sets &nbsp;|&nbsp; %s'
                '</font>'
                % (sc.hexval(), a["display"], TEXT_MUTED.hexval(),
                   avg, cp, a["max_rep"], a["max_set"], rating_lbl),
                S["ExTitle"]))

            # LLM feedback or fallback
            fb = ex_fb.get(key, "")
            if not fb:
                fb = (
                    f"The patient performed {a['display']} with an average score of "
                    f"{avg:.1f}/50 and {cp:.0f}% correct form over {a['n']} frames. "
                    f"{'Good technique maintained.' if cp > 50 else 'Recommend focusing on form correction in next session.'}"
                )

            border_c = SUCCESS if avg >= 35 else (WARNING if avg >= 20 else DANGER)
            bg_c = SUCCESS_LIGHT if avg >= 35 else (WARNING_LIGHT if avg >= 20 else DANGER_LIGHT)
            story.append(_coloured_box(
                Paragraph(fb, S["LLMBody"]), bg_c, border_colour=border_c))
            story.append(Spacer(1, 3*mm))

    # ━━━━ 7. SCORE TIMELINE CHART ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if frames and len(frames) > 1:
        story.append(_section("Score Timeline", S))
        story.append(Paragraph(
            "Frame-by-frame quality score progression across the session.",
            ParagraphStyle("tdesc", parent=S["Normal"],
                           textColor=TEXT_MUTED, fontSize=8.5, spaceAfter=3*mm)))

        ex_fr = defaultdict(list)
        for i, f in enumerate(frames):
            en = _field(f, 'exercise_name', '')
            if not _is_selected(en):
                continue
            if _norm(en) in SKIP:
                continue
            sc = float(_field(f, 'score', 0))
            ex_fr[_norm(en)].append((i, sc))

        line_colors = [PRIMARY, ACCENT, SUCCESS, WARNING, DANGER,
                       colors.HexColor("#17a2b8"), colors.HexColor("#fd7e14")]
        data_sets = []
        legend_labels = []
        for idx, (nk, pts) in enumerate(ex_fr.items()):
            if len(pts) > 200:
                step = max(1, len(pts)//200)
                pts = pts[::step]
            data_sets.append(pts)
            legend_labels.append(ex_agg.get(nk, {}).get("display", _title(nk)))

        if data_sets:
            drawing = Drawing(CW, 130)
            plot = LinePlot()
            plot.x = 40; plot.y = 20
            plot.width = float(CW) - 60; plot.height = 95
            plot.data = data_sets
            for i in range(len(data_sets)):
                plot.lines[i].strokeColor = line_colors[i % len(line_colors)]
                plot.lines[i].strokeWidth = 1.4
            plot.xValueAxis.valueMin = 0
            plot.xValueAxis.labels.fontSize = 7
            plot.xValueAxis.labels.fillColor = TEXT_MUTED
            plot.yValueAxis.valueMin = 0
            plot.yValueAxis.valueMax = 50
            plot.yValueAxis.valueStep = 10
            plot.yValueAxis.labels.fontSize = 7
            plot.yValueAxis.labels.fillColor = TEXT_MUTED
            drawing.add(plot)
            story.append(drawing)

            legend_parts = [
                '<font color="%s">■</font> %s' % (line_colors[i%len(line_colors)].hexval(), l)
                for i, l in enumerate(legend_labels)
            ]
            story.append(Paragraph(
                "&nbsp;&nbsp;&nbsp;".join(legend_parts),
                ParagraphStyle("leg", parent=S["Normal"],
                               alignment=TA_CENTER, fontSize=8, spaceAfter=4*mm)))
        else:
            story.append(Paragraph("<i>No scoreable frames recorded for selected exercises.</i>",
                                   S["CenterMuted"]))
        story.append(Spacer(1, 4*mm))

    # ━━━━ 8. DETAILED PERFORMANCE METRICS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if ex_agg:
        story.append(_section("Detailed Performance Metrics", S))
        phdr = ["Exercise", "Program", "Avg Score", "Correct %",
                "Frames", "Reps", "Sets", "Rating"]
        prows = [phdr]
        for key, a in ex_agg.items():
            avg = a["total"] / a["n"] if a["n"] else 0
            cp  = a["correct"] / a["n"] * 100 if a["n"] else 0
            plbl = "Low Back Pain" if a["prog"] == "low_back_pain" else "General"
            pc = _pct_col(cp)
            rc = _score_col(avg)
            prows.append([
                a["display"], plbl,
                Paragraph('<font color="%s"><b>%.1f</b></font>' % (rc.hexval(), avg), S["Normal"]),
                Paragraph('<font color="%s"><b>%.0f%%</b></font>' % (pc.hexval(), cp), S["Normal"]),
                str(a["n"]), str(a["max_rep"]), str(a["max_set"]),
                Paragraph('<font color="%s"><b>%s</b></font>' % (rc.hexval(), _score_label(avg)), S["Normal"]),
            ])
        pcw = [CW*f for f in (0.18, 0.12, 0.10, 0.11, 0.10, 0.08, 0.08, 0.14)]
        pt = Table(prows, colWidths=pcw, repeatRows=1)
        pt.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,0), PRIMARY_DARK),
            ("TEXTCOLOR",      (0,0),(-1,0), WHITE),
            ("FONTNAME",       (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0),(-1,-1), 8),
            ("ALIGN",          (1,0),(-1,-1), "CENTER"),
            ("ALIGN",          (0,0),(0,-1), "LEFT"),
            ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
            ("GRID",           (0,0),(-1,-1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [WHITE, LIGHT_BG]),
            ("TOPPADDING",     (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 4),
            ("LEFTPADDING",    (0,0),(-1,-1), 5),
        ]))
        story.append(pt)
        story.append(Spacer(1, 5*mm))

    # ━━━━ 9. AI SESSION SUMMARY & RECOMMENDATIONS ━━━━━━━━━━━━━━━━━━━━━
    story.append(_section("AI Session Summary &amp; Recommendations", S))

    if session_summary_text:
        bg = INFO_BG2 if not needs_center else WARM_BG
        bc = PRIMARY if not needs_center else WARNING
        story.append(_coloured_box(
            Paragraph(session_summary_text, S["LLMBody"]), bg, border_colour=bc))
    else:
        fb_text = (
            f"Session quality score: <b>{quality:.1f}/50</b> ({_score_label(quality)}). "
            f"Completion: <b>{comp_perc:.0f}%</b>. "
            f"Pain level {'improved' if pain_a < pain_b else 'unchanged'} "
            f"from {pain_b} to {pain_a}. "
        )
        if needs_center:
            fb_text += (
                f"<br/><br/><b>Recommendation:</b> Quality is below the threshold "
                f"({CENTER_VISIT_SCORE_THRESHOLD:.0f}/50). "
                "An in-person center visit is strongly recommended for supervised guidance."
            )
        else:
            fb_text += "The patient can safely continue home-based rehabilitation."
        story.append(_coloured_box(
            Paragraph(fb_text, S["LLMBody"]),
            INFO_BG2 if not needs_center else WARNING_LIGHT,
            border_colour=PRIMARY if not needs_center else WARNING))
    story.append(Spacer(1, 3*mm))

    # ── center-visit alert banner ──
    if needs_center:
        story.append(_coloured_box(
            Paragraph(
                '<b>Action Required:</b> Aggregate quality score (%.1f/50) is below '
                'the recommended threshold. Please book an appointment at your nearest '
                'rehabilitation center for supervised exercise training before '
                'continuing home exercises.' % quality,
                S["AlertText"]),
            DANGER_LIGHT, border_colour=DANGER))
        story.append(Spacer(1, 4*mm))

    # ━━━━ 10. NEXT STEPS & ACTION ITEMS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    story.append(_section("Next Steps &amp; Action Items", S))
    if next_steps_text:
        lines = [l.strip() for l in next_steps_text.strip().split("\n") if l.strip()]
        for line in lines:
            story.append(Paragraph(
                '<font color="%s">•</font> %s' % (PRIMARY_DARK.hexval(),
                    line.lstrip("0123456789.-) ")),
                S["StepItem"]))
            story.append(Spacer(1, 1.5*mm))
    else:
        defaults = [
            "Continue practising the prescribed exercises at home, focusing on correct form.",
            "Monitor pain levels — if pain increases, reduce intensity and consult your therapist.",
            "Aim to increase repetitions gradually over the next two sessions.",
            "Schedule a follow-up session within 1-2 weeks to reassess progress.",
        ]
        if needs_center:
            defaults.insert(0,
                "Book an in-person appointment at the rehabilitation center for supervised guidance.")
        for d in defaults:
            story.append(Paragraph(
                '<font color="%s">•</font> %s' % (PRIMARY_DARK.hexval(), d),
                S["StepItem"]))
            story.append(Spacer(1, 1.5*mm))
    story.append(Spacer(1, 6*mm))

    # ━━━━ 11. DISCLAIMER ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=3*mm))
    story.append(Paragraph(
        "This report is auto-generated by <b>Home Rehab Coach</b> and is intended "
        "as a supplementary tool for clinical decision-making. AI-generated insights "
        "are powered by Groq LLM and should not replace professional medical assessment. "
        "Please consult your physiotherapist or physician for clinical interpretation.",
        ParagraphStyle("Disclaimer", parent=S["Normal"],
                       textColor=TEXT_MUTED, fontSize=7, alignment=TA_CENTER)))

    # ── build ──
    doc.build(story, onFirstPage=_chrome, onLaterPages=_chrome)
    return buf.getvalue()
