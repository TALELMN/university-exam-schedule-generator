"""Course-code extraction and canonicalization."""

from __future__ import annotations

import re

DEFAULT_PATTERN = r"[A-Z]{2,5}\s?[0-9]{3,4}"
SUSPICIOUS_PATTERN = r"[A-Z]{2,5}\s?[A-Z0-9IO]{3,4}"


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def has_code_boundaries(text: str, start: int, end: int) -> bool:
    """Avoid finding course-like substrings embedded in ordinary words."""
    return not ((start > 0 and text[start - 1].isalnum()) or
                (end < len(text) and text[end].isalnum()))


def is_academic_year_code(code: str) -> bool:
    """Exclude semester headings such as FALL2026 from course-code matches."""
    return bool(re.fullmatch(r"(?:FALL|SPRING|SUMMER|WINTER)20\d{2}", code.upper()))


def extract_course_codes(text: str, pattern: str = DEFAULT_PATTERN) -> list[str]:
    """Extract, normalize, and de-duplicate course codes in first-seen order."""
    try:
        expression = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid course-code regex: {exc}") from exc
    found: list[str] = []
    seen: set[str] = set()
    for match in expression.finditer(text or ""):
        code = normalize_code(match.group(0))
        if (code and code not in seen and not is_academic_year_code(code)
                and has_code_boundaries(text or "", match.start(), match.end())):
            seen.add(code)
            found.append(code)
    return found


def extract_suspicious_codes(text: str, valid_pattern: str = DEFAULT_PATTERN,
                             suspicious_pattern: str = SUSPICIOUS_PATTERN) -> list[str]:
    """Find code-shaped OCR strings with letters in their numeric suffix."""
    valid = set(extract_course_codes(text, valid_pattern))
    result: list[str] = []
    try:
        expression = re.compile(suspicious_pattern, re.IGNORECASE)
    except re.error:
        expression = re.compile(SUSPICIOUS_PATTERN, re.IGNORECASE)
    for match in expression.finditer(text or ""):
        raw = normalize_code(match.group(0))
        if is_academic_year_code(raw) or not has_code_boundaries(text or "", match.start(), match.end()):
            continue
        # Try the plausible 2-5 letter prefix / 3-4 digit suffix split. OCR can
        # turn the first numeric character into I/O, making the prefix ambiguous.
        has_ocr_digit = any(
            len(raw[:split]) in range(2, 6)
            and len(raw[split:]) in range(3, 5)
            and re.fullmatch(r"[A-Z]{2,5}", raw[:split])
            and re.search(r"\d", raw[split:])
            and sum(character.isdigit() for character in raw[split:]) >= 2
            and re.search(r"[IO]", raw[split:])
            for split in range(2, min(6, len(raw) - 2))
        )
        if raw not in valid and has_ocr_digit and raw not in result:
            result.append(raw)
    return result
