from exam_scheduler.matching.matcher import rebuild_matches, unassigned_exam_codes
from exam_scheduler.models import AnalysisResult, ExamRecord, LevelTimetable
from exam_scheduler.output.common import rows_for_level


def _sample_result():
    result = AnalysisResult(levels=[LevelTimetable(
        name="Freshman 5", source="Freshman 5.png",
        codes=["ECO171", "ENG111", "ECE143", "CS101", "MATH141", "PHYS151", "ECE143"],
    )])
    samples = [
        ("ECO171", "Introduction to Microeconomics", "2026-10-11", "Saturday", "08:30", "10:30"),
        ("ENG111", "Academic English", "2026-10-12", "Monday", "08:30", "10:30"),
        ("ECE143", "Digital Systems", "2026-10-13", "Tuesday", "13:30", "15:30"),
        ("CS101", "Introduction to Programming", "2026-10-14", "Wednesday", "11:00", "13:00"),
        ("PHYS151", "Classical Mechanics", "2026-10-16", "Friday", "13:30", "15:30"),
        ("MATH141", "Calculus I", "2026-10-17", "Saturday", "08:30", "10:30"),
        ("CS999", "Unassigned course", "2026-10-18", "Sunday", "08:30", "10:30"),
    ]
    result.exams = {row[0]: ExamRecord(code=row[0], course_name=row[1], date=row[2], day=row[3],
                                       start_time=row[4], end_time=row[5]) for row in samples}
    rebuild_matches(result)
    return result


def test_example_matches_once_per_code_and_sorts_chronologically():
    result = _sample_result()
    rows = rows_for_level(result, "Freshman 5")
    assert [row.code for row in rows] == ["ECO171", "ENG111", "ECE143", "CS101", "PHYS151", "MATH141"]
    assert len([row for row in rows if row.code == "ECE143"]) == 1
    assert all(row.status == "Matched" for row in rows)
    assert unassigned_exam_codes(result) == ["CS999"]


def test_missing_courses_remain_visible():
    result = _sample_result()
    result.levels[0].codes.append("CS998")
    rebuild_matches(result)
    assert any(row.code == "CS998" and row.status == "Missing" for row in result.matches)
