"""Connect level course codes to the official exam timetable by code only."""

from __future__ import annotations

import logging

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.normalizer import normalize_code
from exam_scheduler.models import AnalysisResult, CourseMatch, SourceFile
from exam_scheduler.parser.exam_parser import parse_exam_schedule
from exam_scheduler.parser.timetable_parser import group_level_name, merge_level_sections, parse_timetable

LOGGER = logging.getLogger("exam_scheduler")


def analyze_sources(timetables: list[SourceFile], exam_pdf: SourceFile,
                    config: AppConfig) -> AnalysisResult:
    result = AnalysisResult(exam_source=exam_pdf.name, files_attempted=len(timetables) + 1)
    for source in timetables:
        try:
            level = parse_timetable(source, config)
            result.levels.append(level)
            result.warnings.extend(f"{level.name}: {warning}" for warning in level.warnings)
            if level.ocr_used:
                result.ocr_warnings.append((level.name, f"OCR was used for {source.name}. Check extracted codes."))
        except Exception as exc:
            message = f"{source.name}: {exc}"
            LOGGER.exception("Failed to process timetable %s", source.name)
            result.errors.append(message)
    result.levels = merge_level_sections(result.levels, config.group_numbered_sections)
    if config.group_numbered_sections:
        result.ocr_warnings = [(group_level_name(level), warning) for level, warning in result.ocr_warnings]
    try:
        result.exams, exam_warnings, exam_ocr = parse_exam_schedule(exam_pdf, config)
        result.warnings.extend(f"Exam PDF: {warning}" for warning in exam_warnings)
        if exam_ocr:
            result.ocr_warnings.append(("Exam timetable", "OCR was used for the exam PDF. Check extracted records."))
    except Exception as exc:
        message = f"{exam_pdf.name}: {exc}"
        LOGGER.exception("Failed to process exam timetable %s", exam_pdf.name)
        result.errors.append(message)
    rebuild_matches(result)
    return result


def rebuild_matches(result: AnalysisResult) -> None:
    """Recompute only the inexpensive code-to-record matching after user edits."""
    exam_index = {normalize_code(code): exam for code, exam in result.exams.items()}
    matches: list[CourseMatch] = []
    for level in result.levels:
        # Course repetitions for multiple weekly sessions collapse to one exam row.
        level.codes = list(dict.fromkeys(normalize_code(code) for code in level.codes if normalize_code(code)))
        for code in level.codes:
            exam = exam_index.get(code)
            if exam:
                status = "Matched" if exam.date and exam.start_time and exam.end_time else "Needs review"
                note = "" if status == "Matched" else "Exam row found, but date or time needs review."
                matches.append(CourseMatch(
                    level=level.name, code=code, course_name=exam.course_name,
                    professors=", ".join(exam.professors), date=exam.date, day=exam.day,
                    start_time=exam.start_time, end_time=exam.end_time,
                    status=status, warning=note,
                ))
            else:
                matches.append(CourseMatch(
                    level=level.name, code=code, status="Missing",
                    warning="No matching exam record was found.",
                ))
    result.matches = matches


def unassigned_exam_codes(result: AnalysisResult) -> list[str]:
    used = {normalize_code(code) for level in result.levels for code in level.codes}
    return sorted(code for code in result.exams if normalize_code(code) not in used)
