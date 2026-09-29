"""Extraction of level names and unique course codes from weekly timetables."""

from __future__ import annotations

import re
from pathlib import Path

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.normalizer import extract_course_codes, extract_suspicious_codes
from exam_scheduler.models import LevelTimetable, SourceFile
from exam_scheduler.parser.document import extract_document


def detect_level_name(filename: str) -> str:
    """Use the filename stem as the level name, preserving its meaningful casing."""
    stem = Path(filename).stem
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .-_")
    return stem or "Unnamed level"


def group_level_name(name: str) -> str:
    """Remove section numbers from academic standing names while keeping programs.

    Examples: ``Sophomore 1`` and ``Sophomore 6`` become ``Sophomore``;
    ``Junior SWE 1`` becomes ``Junior SWE`` while ``Junior CSE`` stays distinct.
    """
    normalized = re.sub(r"_+", " ", name.strip())
    normalized = re.sub(r"^(Freshman|Sophomore|Junior|Senior)-", r"\1 ", normalized, flags=re.I)
    tokens = normalized.split()
    if not tokens or tokens[0].casefold() not in {"freshman", "sophomore", "junior", "senior"}:
        return re.sub(r"\s+", " ", normalized).strip()

    tokens[0] = tokens[0].capitalize()
    rest = tokens[1:]
    # Explicit labels are unambiguous section markers wherever they appear.
    index = 0
    while index < len(rest) - 1:
        if rest[index].casefold() in {"section", "sec", "group", "class"} and rest[index + 1].isdigit():
            del rest[index:index + 2]
        else:
            index += 1
    # Common filename forms: Sophomore 6, Sophomore 6 SWE, Junior SWE 1.
    rest = [token for token in rest if not token.isdigit()]
    return " ".join([tokens[0], *rest]).strip()


def merge_level_sections(levels: list[LevelTimetable], group_numbered: bool = True) -> list[LevelTimetable]:
    """Combine section timetables into one level/program with unique course codes."""
    merged: dict[str, LevelTimetable] = {}
    for level in levels:
        name = group_level_name(level.name) if group_numbered else re.sub(r"\s+", " ", level.name).strip()
        key = name.casefold()
        if key not in merged:
            merged[key] = LevelTimetable(
                name=name, source=level.source, codes=list(level.codes),
                warnings=list(level.warnings), ocr_used=level.ocr_used,
            )
            continue
        target = merged[key]
        target.codes.extend(level.codes)
        if level.source and level.source not in target.source.split("; "):
            target.source = f"{target.source}; {level.source}" if target.source else level.source
        target.warnings.extend(warning for warning in level.warnings if warning not in target.warnings)
        target.ocr_used = target.ocr_used or level.ocr_used

    results = list(merged.values())
    for level in results:
        level.codes = list(dict.fromkeys(level.codes))
        if level.codes:
            level.warnings = [warning for warning in level.warnings if "No course codes were detected" not in warning]
    return results


def parse_timetable(source: SourceFile, config: AppConfig) -> LevelTimetable:
    content = extract_document(source, config)
    codes = extract_course_codes(content.text, config.course_code_pattern)
    warnings = list(content.warnings)
    suspicious = extract_suspicious_codes(
        content.text, config.course_code_pattern, config.suspicious_course_code_pattern
    )
    for code in suspicious:
        if code not in codes:
            codes.append(code)
            warnings.append(f'Suspicious OCR course code "{code}" needs review.')
    if not codes:
        warnings.append("No course codes were detected in this timetable.")
    return LevelTimetable(
        name=detect_level_name(source.name), source=source.name, codes=codes,
        warnings=warnings, ocr_used=content.ocr_used,
    )
