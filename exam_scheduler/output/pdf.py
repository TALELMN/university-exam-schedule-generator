"""Printable PDF schedules generated locally with ReportLab."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from exam_scheduler.models import AnalysisResult
from exam_scheduler.output.common import export_directory, rows_for_level, time_label
from exam_scheduler.utils.dates import display_date


def generate_pdf(result: AnalysisResult, output_dir: str | Path) -> Path:
    directory = export_directory(output_dir)
    path = directory / "University_Exam_Schedules.pdf"
    page_size = landscape(A4)
    doc = SimpleDocTemplate(str(path), pagesize=page_size, rightMargin=14 * mm,
                            leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ScheduleTitle", parent=styles["Title"], textColor=colors.HexColor("#17365D"),
                                 alignment=TA_LEFT, fontSize=18, leading=22)
    cell_style = ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=8, leading=10)
    story = []
    levels = result.levels or []
    for index, level in enumerate(levels):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(escape(level.name.upper()), title_style))
        story.append(Paragraph("University Examination Schedule", styles["Heading2"]))
        if level.warnings:
            story.append(Paragraph(escape("Review notes: " + " | ".join(level.warnings)), styles["Italic"]))
        story.append(Spacer(1, 5 * mm))
        table_data = [["Date", "Day", "Time", "Code", "Course", "Professor(s)", "Status"]]
        for row in rows_for_level(result, level.name):
            table_data.append([
                display_date(row.date), row.day or "—", time_label(row.start_time, row.end_time),
                row.code, Paragraph(escape(row.course_name or ("Unknown" if row.status == "Missing" else "")), cell_style),
                Paragraph(escape(row.professors or ""), cell_style), row.status,
            ])
        if len(table_data) == 1:
            table_data.append(["—", "—", "—", "—", "No courses extracted", "", "Review"])
        table = Table(table_data, colWidths=[25 * mm, 27 * mm, 33 * mm, 22 * mm, 85 * mm, 45 * mm, 25 * mm],
                      repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D3DF")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    if not levels:
        story.append(Paragraph("No timetable levels were processed.", styles["Title"]))
    doc.build(story)
    return path
