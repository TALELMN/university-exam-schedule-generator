"""Shared ordering, labels, and filename helpers for exports."""

from __future__ import annotations

import re
from pathlib import Path

from exam_scheduler.models import AnalysisResult, CourseMatch


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return (value.strip("_-") or "Level")[:100]


def safe_sheet_name(value: str) -> str:
    value = re.sub(r"[\\/*?:\[\]]", "_", value).strip("' ")
    return (value or "Level")[:31]


def schedule_order(row: CourseMatch) -> tuple[str, str, str]:
    return (row.date or "9999-99-99", row.start_time or "99:99", row.code)


def rows_for_level(result: AnalysisResult, level: str) -> list[CourseMatch]:
    return sorted((row for row in result.matches if row.level == level), key=schedule_order)


def time_label(start: str, end: str) -> str:
    if start and end:
        return f"{start}-{end}"
    return start or "—"


def export_directory(path: str | Path) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output
