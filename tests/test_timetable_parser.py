import pymupdf as fitz

from exam_scheduler.config import AppConfig
from exam_scheduler.models import SourceFile
from exam_scheduler.parser.timetable_parser import parse_timetable


def test_weekly_pdf_extracts_unique_codes_and_filename_level():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((40, 40), "ECO171 ENG111 ECE143 CS101 MATH141 PHYS151 ECE143")
    content = document.tobytes()
    document.close()
    level = parse_timetable(
        SourceFile(name="Freshman_5.pdf", data=content),
        AppConfig(ocr_enabled=False),
    )
    assert level.name == "Freshman 5"
    assert level.codes == ["ECO171", "ENG111", "ECE143", "CS101", "MATH141", "PHYS151"]
