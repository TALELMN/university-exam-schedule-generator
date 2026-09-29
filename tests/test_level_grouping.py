import pymupdf as fitz
from openpyxl import load_workbook

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.matcher import analyze_sources
from exam_scheduler.models import SourceFile
from exam_scheduler.output.generate import generate_outputs
from exam_scheduler.parser.timetable_parser import group_level_name


def _pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 48), text, fontsize=10)
    content = document.tobytes()
    document.close()
    return content


def test_section_numbers_collapse_but_program_names_remain_distinct():
    assert group_level_name("Sophomore 1") == "Sophomore"
    assert group_level_name("Sophomore 6") == "Sophomore"
    assert group_level_name("Freshman 5") == "Freshman"
    assert group_level_name("Junior SWE 1") == "Junior SWE"
    assert group_level_name("Sophomore 1 CSE") == "Sophomore CSE"
    assert group_level_name("Junior CSE") == "Junior CSE"
    assert group_level_name("Sophomore Section 6") == "Sophomore"


def test_multiple_section_timetables_make_one_combined_level_schedule(tmp_path):
    level_sources = [
        SourceFile(name="Sophomore 1.pdf", data=_pdf("ECO171")),
        SourceFile(name="Sophomore 6.pdf", data=_pdf("ENG111")),
    ]
    exam_source = SourceFile(name="Exams.pdf", data=_pdf(
        "ECO171 | Economics | Saturday, October 11 | 08:30-10:30\n"
        "ENG111 | English | Monday, October 12 | 08:30-10:30"
    ))
    result = analyze_sources(level_sources, exam_source, AppConfig(ocr_enabled=False))

    assert len(result.levels) == 1
    assert result.levels[0].name == "Sophomore"
    assert result.levels[0].source == "Sophomore 1.pdf; Sophomore 6.pdf"
    assert [match.code for match in result.matches] == ["ECO171", "ENG111"]
    assert all(match.level == "Sophomore" and match.status == "Matched" for match in result.matches)
    generate_outputs(result, tmp_path, AppConfig(generate_pdf=False, generate_html=False))
    workbook = load_workbook(tmp_path / "University_Exam_Schedules.xlsx", read_only=True)
    assert workbook.sheetnames == ["Summary", "Sophomore"]
    workbook.close()
    assert (tmp_path / "Sophomore.xlsx").is_file()
    assert not (tmp_path / "Sophomore_1.xlsx").exists()


def test_section_grouping_can_be_disabled():
    result = analyze_sources(
        [SourceFile(name="Sophomore 1.pdf", data=_pdf("ECO171")),
         SourceFile(name="Sophomore 6.pdf", data=_pdf("ENG111"))],
        SourceFile(name="Exams.pdf", data=_pdf("ECO171 | Econ | Oct 11 | 08:30-10:30")),
        AppConfig(ocr_enabled=False, group_numbered_sections=False),
    )
    assert [level.name for level in result.levels] == ["Sophomore 1", "Sophomore 6"]
