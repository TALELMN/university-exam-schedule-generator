"""Analysis counts and human-readable validation report."""

from __future__ import annotations

from collections import defaultdict

from exam_scheduler.matching.matcher import unassigned_exam_codes
from exam_scheduler.models import AnalysisResult


def validation_counts(result: AnalysisResult) -> dict[str, int]:
    missing = sum(row.status == "Missing" for row in result.matches)
    matched = sum(row.status == "Matched" for row in result.matches)
    review = sum(row.status == "Needs review" for row in result.matches)
    unique_courses = len({row.code for row in result.matches})
    return {
        "files_processed": result.source_files_processed,
        "levels_detected": len(result.levels),
        "courses_extracted": len(result.matches),
        "unique_courses": unique_courses,
        "exam_records": len(result.exams),
        "successfully_matched": matched,
        "missing_exam_information": missing,
        "records_needing_review": review,
        "ocr_warnings": len(result.ocr_warnings),
        "unassigned_exam_courses": len(unassigned_exam_codes(result)),
        "processing_errors": len(result.errors),
    }


def validation_report(result: AnalysisResult) -> str:
    counts = validation_counts(result)
    missing: dict[str, list[str]] = defaultdict(list)
    for row in result.matches:
        if row.status == "Missing":
            missing[row.level].append(row.code)
    lines = ["=" * 40, "VALIDATION REPORT", "=" * 40, ""]
    labels = [
        ("files_processed", "Files processed"), ("levels_detected", "Levels detected"),
        ("courses_extracted", "Courses extracted"), ("unique_courses", "Unique courses"),
        ("exam_records", "Exam records"), ("successfully_matched", "Successfully matched"),
        ("missing_exam_information", "Missing exam information"),
        ("records_needing_review", "Records needing review"), ("ocr_warnings", "OCR warnings"),
        ("unassigned_exam_courses", "Unassigned exam courses"), ("processing_errors", "Processing errors"),
    ]
    lines.extend(f"{label}: {counts[key]}" for key, label in labels)
    lines += ["", "-" * 40, "MISSING EXAMS"]
    if missing:
        for level, codes in sorted(missing.items()):
            lines.append(level)
            lines.extend(f"  {code}" for code in sorted(set(codes)))
    else:
        lines.append("  None")
    lines += ["", "-" * 40, "OCR WARNINGS"]
    if result.ocr_warnings:
        lines.extend(f"{level}\n  {message}" for level, message in result.ocr_warnings)
    else:
        lines.append("  None")
    lines += ["", "-" * 40, "UNASSIGNED EXAM COURSES"]
    extras = unassigned_exam_codes(result)
    if extras:
        for code in extras:
            exam = result.exams[code]
            lines.append(f"  {code} | {exam.course_name or 'Unknown'}")
    else:
        lines.append("  None")
    if result.errors:
        lines += ["", "-" * 40, "PROCESSING ERRORS"]
        lines.extend(f"  {error}" for error in result.errors)
    if result.warnings:
        lines += ["", "-" * 40, "OTHER WARNINGS"]
        lines.extend(f"  {warning}" for warning in result.warnings)
    lines += ["", "=" * 40]
    return "\n".join(lines)
