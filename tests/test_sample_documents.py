from pathlib import Path

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.matcher import analyze_sources
from exam_scheduler.models import SourceFile
from exam_scheduler.output.common import rows_for_level


def test_included_sample_pdfs_run_end_to_end():
    sample_dir = Path(__file__).parents[1] / "examples" / "sample_input"
    timetable_path = sample_dir / "Freshman 5.pdf"
    exam_path = sample_dir / "Midterm Exams Schedule - Fall 2026.pdf"
    result = analyze_sources(
        [SourceFile(name=timetable_path.name, path=timetable_path)],
        SourceFile(name=exam_path.name, path=exam_path),
        AppConfig.load(Path(__file__).parents[1] / "config.json"),
    )
    assert [level.name for level in result.levels] == ["Freshman"]
    assert [row.code for row in rows_for_level(result, "Freshman")] == [
        "ECO171", "ENG111", "ECE143", "CS101", "PHYS151", "MATH141"
    ]
    assert all(row.status == "Matched" for row in result.matches)
    assert not result.warnings
