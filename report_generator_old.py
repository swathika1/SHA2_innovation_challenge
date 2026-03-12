"""
report_generator.py — Generate attractive PDF medical rehabilitation reports.

Uses ReportLab to produce a single-page (or multi-page) summary of a
patient's exercise session including:
  • Patient info & session metadata
  • Overall statistics (quality score, pain, effort, duration)
  • Per-exercise breakdown with completion bars
  • Frame-level score timeline chart
  • Professional header/footer with clinic logo
"""

import io
import os
import math
from datetime import datetime
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderPDF

# ──────────────────────────── colour palette ─────────────────────────────
PRIMARY = colors.HexColor("#667eea")
PRIMARY_DARK = colors.HexColor("#5a67d8")
ACCENT = colors.HexColor("#764ba2")
SUCCESS = colors.HexColor("#28a745")
WARNING = colors.HexColor("#ffc107")
DANGER = colors.HexColor("#dc3545")
LIGHT_BG = colors.HexColor("#f8f9fa")
BORDER = colors.HexColor("#dee2e6")
TEXT_DARK = colors.HexColor("#212529")
TEXT_MUTED = colors.HexColor("#6c757d")

PAGE_W, PAGE_H = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

LOGO_PATH = os.path.join(os.path.dirname(__file__), "static", "rehab-logo.png")


# ──────────────────────────── helpers ────────────────────────────────────
def _fmt_duration(seconds):
    if seconds is None:
        return "--"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def _score_colour(score, max_score=50.0):
    """Return green/yellow/red based on a normalised 0-100 %."""
    pct = (score / max_score * 100) if max_score else 0
    if pct >= 70:
        return SUCCESS
    elif pct >= 40:
        return WARNING
    return DANGER


def _perc_colour(pct):
    if pct >= 100:
        return SUCCESS
    elif pct >= 50:
        return WARNING
    return DANGER


# ──────────────────────────── page chrome ────────────────────────────────
def _header_footer(canvas, doc):
    """Draw header bar + footer on every page."""
    canvas.saveState()

    # ── header gradient bar ─────────────────────────────────────────────
    bar_h = 22 * mm
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H - bar_h, PAGE_W, bar_h, fill=1, stroke=0)
    # subtle accent overlay on right third
    canvas.setFillColor(ACCENT)
    canvas.rect(PAGE_W * 0.6, PAGE_H - bar_h, PAGE_W * 0.4, bar_h, fill=1, stroke=0)

    # logo (if available)
    if os.path.exists(LOGO_PATH):
        try:
            canvas.drawImage(
                LOGO_PATH,
                LEFT_MARGIN, PAGE_H - bar_h + 3 * mm,
                width=16 * mm, height=16 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(LEFT_MARGIN + 20 * mm, PAGE_H - bar_h + 7 * mm, "Home Rehab Coach")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(LEFT_MARGIN + 20 * mm, PAGE_H - bar_h + 2.5 * mm, "Rehabilitation Session Report")

    # date on the right
    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(
        PAGE_W - RIGHT_MARGIN,
        PAGE_H - bar_h + 4 * mm,
        datetime.now().strftime("Generated %d %b %Y, %H:%M"),
    )

    # ── footer ──────────────────────────────────────────────────────────
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(LEFT_MARGIN, 14 * mm, PAGE_W - RIGHT_MARGIN, 14 * mm)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(LEFT_MARGIN, 10 * mm, "Confidential — For Medical Use Only")
    canvas.drawRightString(
        PAGE_W - RIGHT_MARGIN, 10 * mm,
        f"Page {canvas.getPageNumber()}",
    )

    canvas.restoreState()


# ──────────────────────────── public API ─────────────────────────────────
def generate_session_report(
    patient_name: str,
    patient_condition: str,
    session_data: dict,
    exercises: list,
    frames: list,
    overall_duration: int | None = None,
) -> bytes:
    """Return the PDF as an in-memory bytes buffer.

    Parameters
    ----------
    patient_name : str
    patient_condition : str
    session_data : dict-like (sqlite3.Row)
        Must contain: quality_score, completed_perc, pain_before, pain_after,
                      effort_level, started_at, completed_at
    exercises : list[dict]
        Each dict: exercise_name, quality_score, completion_perc,
                   sets_required (dict), sets_completed (dict), duration_seconds
    frames : list[dict-like]
        Rows from session_frames: timestamp, exercise_name, score, status,
                                  rep_count, set_count, program
    overall_duration : int | None  (seconds)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=LEFT_MARGIN,
        rightMargin=RIGHT_MARGIN,
        topMargin=30 * mm,   # room for header
        bottomMargin=22 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("SectionTitle", parent=styles["Heading2"],
                              textColor=PRIMARY_DARK, fontSize=13,
                              spaceAfter=4 * mm, spaceBefore=6 * mm))
    styles.add(ParagraphStyle("CardLabel", parent=styles["Normal"],
                              textColor=TEXT_MUTED, fontSize=8))
    styles.add(ParagraphStyle("CardValue", parent=styles["Normal"],
                              textColor=TEXT_DARK, fontSize=16,
                              fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("CenterSmall", parent=styles["Normal"],
                              alignment=TA_CENTER, textColor=TEXT_MUTED,
                              fontSize=8))

    story = []

    # ────────────────── patient info banner ──────────────────────────────
    quality = float(session_data.get('quality_score', 0) or 0)
    completed_perc = float(session_data.get('completed_perc', 0) or 0)
    pain_before = int(session_data.get('pain_before', 0) or 0)
    pain_after = int(session_data.get('pain_after', 0) or 0)
    effort = int(session_data.get('effort_level', 5) or 5)
    started_at = session_data.get('started_at', '') or ''

    info_data = [
        ["Patient", patient_name or "N/A"],
        ["Condition", patient_condition or "General Rehabilitation"],
        ["Session Date", started_at[:16].replace("T", "  ") if started_at else "N/A"],
        ["Duration", _fmt_duration(overall_duration)],
    ]
    info_table = Table(info_data, colWidths=[35 * mm, CONTENT_W - 35 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY_DARK),
        ("TEXTCOLOR", (1, 0), (1, -1), TEXT_DARK),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # ────────────────── stat cards row ───────────────────────────────────
    story.append(Paragraph("Overall Performance", styles["SectionTitle"]))

    card_w = CONTENT_W / 4 - 2 * mm

    def _card(label, value, colour=TEXT_DARK):
        return [
            Paragraph(f'<font color="{colour.hexval()}" size="18"><b>{value}</b></font>',
                      styles["Normal"]),
            Paragraph(f'<font color="{TEXT_MUTED.hexval()}" size="8">{label}</font>',
                      styles["Normal"]),
        ]

    cards_data = [
        _card("Quality Score", f"{quality:.1f}/50", _score_colour(quality)),
        _card("Completion", f"{completed_perc:.0f}%", _perc_colour(completed_perc)),
        _card("Pain Change", f"{pain_before} → {pain_after}",
              SUCCESS if pain_after <= pain_before else DANGER),
        _card("Effort", f"{effort}/10", TEXT_DARK),
    ]

    # Build a 1-row table of 4 mini-tables (cards)
    card_tables = []
    for card in cards_data:
        t = Table([[card[0]], [card[1]]], colWidths=[card_w])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        card_tables.append(t)

    row_table = Table([card_tables], colWidths=[card_w + 2*mm]*4)
    row_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(row_table)
    story.append(Spacer(1, 6 * mm))

    # ────────────────── exercise breakdown table ─────────────────────────
    if exercises:
        story.append(Paragraph("Exercise Breakdown", styles["SectionTitle"]))

        header = ["Exercise", "Quality", "Completion", "Sets (Done/Target)", "Time"]
        rows = [header]
        for ex in exercises:
            ex_name = ex.get("exercise_name", "")
            ex_quality = float(ex.get("quality_score", 0) or 0)
            ex_perc = float(ex.get("completion_perc", 0) or 0)
            sets_req = ex.get("sets_required") or {}
            sets_comp = ex.get("sets_completed") or {}
            total_req = sum(int(v) for v in sets_req.values()) if isinstance(sets_req, dict) else 0
            total_comp = sum(int(v) for v in sets_comp.values()) if isinstance(sets_comp, dict) else 0
            dur = ex.get("duration_seconds")

            perc_colour = _perc_colour(ex_perc)
            perc_html = (
                f'<font color="{perc_colour.hexval()}"><b>{ex_perc:.0f}%</b></font>'
            )

            rows.append([
                ex_name,
                f"{ex_quality:.1f}",
                Paragraph(perc_html, styles["Normal"]),
                f"{total_comp} / {total_req}",
                _fmt_duration(dur),
            ])

        col_widths = [CONTENT_W * f for f in (0.28, 0.14, 0.18, 0.22, 0.18)]
        ex_table = Table(rows, colWidths=col_widths, repeatRows=1)
        ex_table.setStyle(TableStyle([
            # header
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(ex_table)
        story.append(Spacer(1, 6 * mm))

    # ────────────────── frame-level score timeline ───────────────────────
    if frames and len(frames) > 1:
        story.append(Paragraph("Score Timeline", styles["SectionTitle"]))
        story.append(Paragraph(
            "Frame-by-frame quality score over the session. "
            "Green zones indicate correct form; red indicates form that needs improvement.",
            ParagraphStyle("TimelineDesc", parent=styles["Normal"],
                           textColor=TEXT_MUTED, fontSize=8, spaceAfter=3*mm),
        ))

        # Build per-exercise colour-coded line plot
        # Group frames by exercise
        ex_frames = defaultdict(list)
        for i, f in enumerate(frames):
            ex_name = f['exercise_name'] if hasattr(f, '__getitem__') else getattr(f, 'exercise_name', '')
            score = float(f['score'] if hasattr(f, '__getitem__') else getattr(f, 'score', 0))
            ex_frames[ex_name].append((i, score))

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
        for idx, (ex_name, pts) in enumerate(ex_frames.items()):
            if not ex_name or ex_name in ("no_pose", "idle", "error", "none", "no_frame"):
                continue
            # Downsample if too many points (keep readability)
            if len(pts) > 200:
                step = max(1, len(pts) // 200)
                pts = pts[::step]
            data_sets.append(pts)
            legend_labels.append(ex_name.replace("_", " ").title())

        if data_sets:
            plot.data = data_sets
            for i in range(len(data_sets)):
                plot.lines[i].strokeColor = line_colors[i % len(line_colors)]
                plot.lines[i].strokeWidth = 1.2

            plot.xValueAxis.valueMin = 0
            plot.xValueAxis.labels.fontSize = 7
            plot.xValueAxis.labels.fillColor = TEXT_MUTED
            plot.xValueAxis.axisLabelText = "Frame"
            plot.yValueAxis.valueMin = 0
            plot.yValueAxis.valueMax = 50
            plot.yValueAxis.valueStep = 10
            plot.yValueAxis.labels.fontSize = 7
            plot.yValueAxis.labels.fillColor = TEXT_MUTED

            drawing.add(plot)

            # Simple legend below chart
            legend_parts = []
            for i, lbl in enumerate(legend_labels):
                c = line_colors[i % len(line_colors)]
                legend_parts.append(
                    f'<font color="{c.hexval()}">■</font> {lbl}'
                )
            story.append(drawing)
            story.append(Paragraph(
                "  &nbsp;&nbsp;".join(legend_parts),
                ParagraphStyle("Legend", parent=styles["Normal"],
                               alignment=TA_CENTER, fontSize=8,
                               spaceAfter=4*mm),
            ))
        else:
            story.append(Paragraph(
                "<i>No scoreable frames recorded.</i>",
                styles["CenterSmall"],
            ))

        story.append(Spacer(1, 4 * mm))

    # ────────────────── per-exercise performance summary ─────────────────
    if frames and len(frames) > 0:
        story.append(Paragraph("Detailed Performance Metrics", styles["SectionTitle"]))

        # Aggregate by exercise
        ex_agg = defaultdict(lambda: {
            "total_score": 0, "count": 0, "correct": 0, "wrong": 0,
            "max_rep": 0, "max_set": 0, "program": "",
        })
        for f in frames:
            ex_name = f['exercise_name'] if hasattr(f, '__getitem__') else getattr(f, 'exercise_name', '')
            if not ex_name or ex_name in ("no_pose", "idle", "error", "none", "no_frame"):
                continue
            score = float(f['score'] if hasattr(f, '__getitem__') else getattr(f, 'score', 0))
            status = f['status'] if hasattr(f, '__getitem__') else getattr(f, 'status', '')
            rep = int(f['rep_count'] if hasattr(f, '__getitem__') else getattr(f, 'rep_count', 0))
            st = int(f['set_count'] if hasattr(f, '__getitem__') else getattr(f, 'set_count', 1))
            prog = f['program'] if hasattr(f, '__getitem__') else getattr(f, 'program', 'general')

            agg = ex_agg[ex_name]
            agg["total_score"] += score
            agg["count"] += 1
            if status == "CORRECT":
                agg["correct"] += 1
            elif status == "WRONG":
                agg["wrong"] += 1
            agg["max_rep"] = max(agg["max_rep"], rep)
            agg["max_set"] = max(agg["max_set"], st)
            agg["program"] = prog

        if ex_agg:
            header = ["Exercise", "Program", "Avg Score", "Correct %",
                      "Frames", "Reps", "Sets"]
            rows = [header]
            for ex_name, agg in ex_agg.items():
                avg_s = agg["total_score"] / agg["count"] if agg["count"] else 0
                correct_pct = agg["correct"] / agg["count"] * 100 if agg["count"] else 0
                prog_label = "Low Back Pain" if agg["program"] == "low_back_pain" else "General"
                pct_color = _perc_colour(correct_pct)
                rows.append([
                    ex_name.replace("_", " ").title(),
                    prog_label,
                    f"{avg_s:.1f}",
                    Paragraph(
                        f'<font color="{pct_color.hexval()}"><b>{correct_pct:.0f}%</b></font>',
                        styles["Normal"]),
                    str(agg["count"]),
                    str(agg["max_rep"]),
                    str(agg["max_set"]),
                ])

            cw = [CONTENT_W * f for f in (0.22, 0.16, 0.12, 0.14, 0.12, 0.10, 0.10)]
            perf_table = Table(rows, colWidths=cw, repeatRows=1)
            perf_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(perf_table)
            story.append(Spacer(1, 6 * mm))

    # ────────────────── disclaimer ───────────────────────────────────────
    story.append(Spacer(1, 8 * mm))
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

    # ── build ───────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
