import pymupdf as fitz

from exam_scheduler.config import AppConfig
from exam_scheduler.models import SourceFile
from exam_scheduler.parser.exam_parser import parse_exam_schedule


def test_text_pdf_exam_record_extraction():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "CS101 | Introduction to Programming | Prof. Ada Lovelace | Wednesday, October 14th | 11.00-13.00")
    content = document.tobytes()
    document.close()
    source = SourceFile(name="official.pdf", data=content)
    records, warnings, ocr_used = parse_exam_schedule(source, AppConfig(ocr_enabled=False, exam_year=2026))
    record = records["CS101"]
    assert record.course_name == "Introduction to Programming"
    assert record.date == "2026-10-14"
    assert record.day == "Wednesday"
    assert (record.start_time, record.end_time) == ("11:00", "13:00")
    assert record.professors == ["Ada Lovelace"]
    assert not ocr_used
    assert not warnings
