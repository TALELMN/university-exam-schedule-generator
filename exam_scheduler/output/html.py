"""Responsive, printable HTML schedule with navigation between levels."""

from __future__ import annotations

import html
from pathlib import Path

from exam_scheduler.models import AnalysisResult
from exam_scheduler.output.common import export_directory, rows_for_level, time_label
from exam_scheduler.utils.dates import display_date


def generate_html(result: AnalysisResult, output_dir: str | Path) -> Path:
    directory = export_directory(output_dir)
    path = directory / "University_Exam_Schedules.html"
    nav = "\n".join(
        f'<a href="#{index}">{html.escape(level.name)}</a>'
        for index, level in enumerate(result.levels)
    )
    sections = []
    for index, level in enumerate(result.levels):
        rows = []
        for row in rows_for_level(result, level.name):
            rows.append(
                "<tr>"
                f"<td>{html.escape(display_date(row.date))}</td><td>{html.escape(row.day or '—')}</td>"
                f"<td>{html.escape(time_label(row.start_time, row.end_time))}</td>"
                f"<td><strong>{html.escape(row.code)}</strong></td>"
                f"<td>{html.escape(row.course_name or ('Unknown' if row.status == 'Missing' else ''))}</td>"
                f"<td>{html.escape(row.professors)}</td>"
                f'<td class="{html.escape(row.status.lower().replace(" ", "-"))}">{html.escape(row.status)}</td>'
                "</tr>"
            )
        sections.append(
            f'<section id="{index}"><h2>{html.escape(level.name)}</h2>'
            '<table><thead><tr><th>Date</th><th>Day</th><th>Time</th><th>Code</th>'
            '<th>Course</th><th>Professor(s)</th><th>Status</th></tr></thead>'
            f'<tbody>{"".join(rows) or "<tr><td colspan=\"7\">No courses extracted</td></tr>"}</tbody></table></section>'
        )
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>University Exam Schedules</title><style>
:root{{--navy:#17365d;--blue:#2368a0;--line:#d8e0e8;--pale:#f2f6fa}}
body{{font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;color:#1c2733;margin:0;background:#f7f9fb}}
header{{background:var(--navy);color:white;padding:2rem max(1rem,calc((100% - 1100px)/2))}}
main{{max-width:1100px;margin:1.5rem auto;padding:0 1rem}} nav{{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1.5rem}}
nav a{{background:white;border:1px solid var(--line);border-radius:5px;padding:.45rem .75rem;color:var(--blue);text-decoration:none}}
section{{background:white;margin:1rem 0;padding:1rem;border:1px solid var(--line);border-radius:8px;break-inside:avoid}}
h1,h2{{margin:.2rem 0 .7rem}}h2{{color:var(--navy)}}table{{border-collapse:collapse;width:100%;font-size:.92rem}}
th{{background:var(--navy);color:white;text-align:left}}th,td{{padding:.65rem;border:1px solid var(--line);vertical-align:top}}
tbody tr:nth-child(even){{background:var(--pale)}}.missing{{color:#a43a25;font-weight:600}}.needs-review{{color:#946200;font-weight:600}}
@media(max-width:750px){{table{{display:block;overflow-x:auto;white-space:nowrap}}}}
@media print{{body{{background:white}}header{{padding:1rem;color:white}}nav{{display:none}}section{{margin:.5rem 0;box-shadow:none}}}}
</style></head><body><header><h1>University Exam Schedules</h1><div>Generated from the official exam timetable and level course lists</div></header>
<main><nav aria-label="Level navigation">{nav}</nav>{''.join(sections)}</main></body></html>"""
    path.write_text(document, encoding="utf-8")
    return path
