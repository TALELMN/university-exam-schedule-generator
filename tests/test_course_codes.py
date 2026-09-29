from exam_scheduler.matching.fuzzy_match import suggest_course_code
from exam_scheduler.matching.normalizer import (
    extract_course_codes,
    extract_suspicious_codes,
    normalize_code,
)


def test_course_codes_normalize_spaces_and_deduplicate():
    text = "CS101 CS 101 ECE 143 MATH141 PHYS 151"
    assert extract_course_codes(text) == ["CS101", "ECE143", "MATH141", "PHYS151"]
    assert normalize_code(" ece 143 ") == "ECE143"


def test_ocr_course_code_is_flagged_and_suggested_not_silently_changed():
    raw = "Weekly plan: ECEI43"
    assert extract_course_codes(raw) == []
    assert extract_suspicious_codes(raw) == ["ECEI43"]
    assert suggest_course_code("ECEI43", ["ECE143"], threshold=90) == ("ECE143", 96)


def test_configurable_course_code_pattern():
    assert extract_course_codes("BIO-1234", r"[A-Z]{3}-\d{4}") == ["BIO1234"]


def test_academic_year_heading_and_word_substrings_are_not_courses():
    text = "Fall 2026 Midterm Examination Schedule\nECO171"
    assert extract_course_codes(text) == ["ECO171"]
    assert extract_suspicious_codes("Weekly Timetable") == []
