"""Structured extraction of exam records from text-based or scanned PDFs."""

from __future__ import annotations

import re
from exam_scheduler.config import AppConfig
from exam_scheduler.matching.normalizer import (
    extract_suspicious_codes,
    has_code_boundaries,
    is_academic_year_code,
    normalize_code,
)
from exam_scheduler.models import ExamRecord, SourceFile
from exam_scheduler.parser.document import extract_document
from exam_scheduler.utils.dates import parse_date, parse_time_range

HEADER_WORDS = ("course code", "course title", "professor", "day/date", "exam date", "time")
MONTH_NAMES = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
DATE_HINT = re.compile(rf"(?:\b(?:{MONTH_NAMES})\b|\b\d{{1,2}}[/-]\d{{1,2}}\b)", re.I)


def _code_spans(text: str, config: AppConfig) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    try:
        valid_expression = re.compile(config.course_code_pattern, re.I)
        suspicious_expression = re.compile(config.suspicious_course_code_pattern, re.I)
    except re.error:
        return spans
    for match in valid_expression.finditer(text):
        raw = normalize_code(match.group(0))
        if (raw and not is_academic_year_code(raw)
                and has_code_boundaries(text, match.start(), match.end())):
            spans.append((match.start(), match.end(), raw))
    for match in suspicious_expression.finditer(text):
        raw = normalize_code(match.group(0))
        if (raw in extract_suspicious_codes(match.group(0), config.course_code_pattern,
                                            config.suspicious_course_code_pattern)
                and has_code_boundaries(text, match.start(), match.end())
                and not any(start == match.start() for start, _, _ in spans)):
            spans.append((match.start(), match.end(), raw))
    return sorted(spans)


def _find_date(block: str, year: int, date_formats: list[str] | None = None) -> tuple[str, str, str] | None:
    for line in block.splitlines():
        line = line.strip(" |\t")
        parsed = parse_date(line, year, date_formats)
        if parsed:
            iso_date, day = parsed
            return iso_date, day, line
        numeric_date = re.search(r"\b\d{1,4}[./-]\d{1,2}[./-]\d{1,4}\b", line)
        if numeric_date:
            parsed = parse_date(numeric_date.group(0), year, date_formats)
            if parsed:
                iso_date, day = parsed
                stated_day = re.search(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", line, re.I)
                if stated_day:
                    day = stated_day.group(1).capitalize()
                return iso_date, day, line
    # Some extracted rows place date and course information on the same line.
    for match in DATE_HINT.finditer(block):
        start = max(0, match.start() - 24)
        end = min(len(block), match.end() + 35)
        snippet = block[start:end].replace("\n", " ")
        parsed = parse_date(snippet, year, date_formats)
        if parsed:
            iso_date, day = parsed
            return iso_date, day, snippet
    return None


def _find_time(block: str, time_formats: list[str] | None = None) -> tuple[str, str, str] | None:
    for line in block.splitlines():
        parsed = parse_time_range(line, time_formats)
        if parsed:
            return parsed[0], parsed[1], line.strip()
    parsed = parse_time_range(block, time_formats)
    if parsed:
        return parsed[0], parsed[1], block.strip()
    return None


def _clean_course_title(block: str, code: str, date_source: str, time_source: str) -> str:
    lines = [line.strip(" |\t") for line in block.splitlines() if line.strip(" |\t")]
    candidates: list[str] = []
    for line in lines:
        if re.fullmatch(r"[|\s]*(?:course code|course title|professors?|day/date(?: of the exam)?|exam date|time)[|\s]*",
                        line, re.I):
            continue
        cleaned = re.sub(re.escape(code), " ", line, flags=re.I)
        cleaned = re.sub(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b[,]?", " ", cleaned, flags=re.I)
        cleaned = re.sub(rf"\b(?:{MONTH_NAMES})\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b\d{1,4}(?:st|nd|rd|th)?\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\d{1,2}[.:]\d{2}\s*(?:[-–—]|to)\s*\d{1,2}[.:]\d{2}", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(?:prof(?:essor)?s?|instructors?|lecturers?)\b\s*:?\s*.*", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"[|,:;\-–—]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and not re.search(r"\b(?:exam|time|date|code|title)\b", cleaned, re.I):
            candidates.append(cleaned)
    # Keep compact, plausible title text; prefer the line that starts beside the code.
    if candidates:
        return max(candidates, key=lambda item: (len(item), item[:1].isupper()))[:240]
    return ""


def _extract_professors(block: str) -> list[str]:
    found: list[str] = []
    for line in block.splitlines():
        match = re.search(r"(?:prof(?:essor)?s?|instructors?|lecturers?)\s*:?\s*(.+)", line, re.I)
        if match:
            professor_text = re.split(r"\||\t", match.group(1), maxsplit=1)[0]
            professor_text = re.sub(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b.*", "", professor_text, flags=re.I)
            names = [part.strip(" ,;|.") for part in re.split(r"[,;]", professor_text)]
            found.extend(name for name in names if name)
    return list(dict.fromkeys(found))


def _record_from_block(code: str, block: str, config: AppConfig) -> ExamRecord:
    date_info = _find_date(block, config.exam_year, config.date_formats)
    time_info = _find_time(block, config.time_formats)
    date_value, day, original_date = date_info or ("", "", "")
    start, end, original_time = time_info or ("", "", "")
    title = _clean_course_title(block, code, original_date, original_time)
    return ExamRecord(
        code=code, course_name=title, professors=_extract_professors(block),
        date=date_value, day=day, start_time=start, end_time=end,
        original_date=original_date, original_time=original_time,
    )


def _parse_table_rows(tables: list[list[list[str]]], config: AppConfig) -> dict[str, ExamRecord]:
    parsed: dict[str, ExamRecord] = {}
    for table in tables:
        headers: list[str] | None = None
        for row in table:
            cells = [(cell or "").strip() for cell in row]
            while cells and not cells[-1]:
                cells.pop()
            normalized_cells = [re.sub(r"\s+", " ", cell).lower() for cell in cells]
            if any(any(word in cell for word in ("course code", "course title", "course name", "professor", "day/date"))
                   for cell in normalized_cells):
                headers = normalized_cells
                continue
            joined = "\n".join(cell for cell in cells if cell)
            spans = _code_spans(joined, config)
            if not spans:
                continue
            # Exam table rows are normally one course per row. If a cell contains multiple
            # codes, each starts a block so a neighboring course cannot inherit its date.
            for index, (_, _, code) in enumerate(spans):
                next_start = spans[index + 1][0] if index + 1 < len(spans) else len(joined)
                block = joined[spans[index][0]:next_start]
                record = _record_from_block(code, block, config)
                if headers:
                    for cell_index, header in enumerate(headers):
                        if cell_index >= len(cells):
                            continue
                        value = cells[cell_index].strip()
                        if "professor" in header and value:
                            record.professors = [part.strip(" ,;|.") for part in re.split(r"[,;|]", value) if part.strip(" ,;|.")]
                        if ("course title" in header or "course name" in header) and value:
                            record.course_name = value
                _merge_record(parsed, record)
    return parsed


def _merge_record(records: dict[str, ExamRecord], record: ExamRecord) -> None:
    current = records.get(record.code)
    if current is None:
        records[record.code] = record
        return
    for field in ("course_name", "date", "day", "start_time", "end_time", "original_date", "original_time"):
        if not getattr(current, field) and getattr(record, field):
            setattr(current, field, getattr(record, field))
    current.professors = list(dict.fromkeys(current.professors + record.professors))


def parse_exam_schedule(source: SourceFile, config: AppConfig) -> tuple[dict[str, ExamRecord], list[str], bool]:
    """Parse exam rows; returns records, parser warnings, and OCR usage."""
    content = extract_document(source, config)
    warnings = list(content.warnings)
    records = _parse_table_rows(content.tables, config)

    text = content.text or ""
    spans = _code_spans(text, config)
    for index, (start, end, code) in enumerate(spans):
        block_end = spans[index + 1][0] if index + 1 < len(spans) else len(text)
        block = text[start:block_end]
        _merge_record(records, _record_from_block(code, block, config))

    if not records:
        warnings.append("No exam course rows were detected. Check the PDF text/OCR and course-code pattern.")
    for record in records.values():
        missing = [label for label, value in (("course title", record.course_name), ("date", record.date),
                                               ("time", record.start_time)) if not value]
        if missing:
            warnings.append(f"{record.code}: could not confidently extract {', '.join(missing)}.")
    return dict(records), warnings, content.ocr_used
