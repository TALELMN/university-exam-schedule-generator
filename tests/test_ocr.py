import pytest
import pymupdf as fitz

from exam_scheduler.matching.fuzzy_match import suggest_course_code
from exam_scheduler.config import AppConfig
from exam_scheduler.models import SourceFile
from exam_scheduler.parser import document as document_parser


@pytest.mark.parametrize("detected,correct", [
    ("CS1O1", "CS101"),
    ("ECEI43", "ECE143"),
    ("MATHI41", "MATH141"),
])
def test_ocr_confusion_is_suggested_with_user_confirmation(detected, correct):
    suggestion = suggest_course_code(detected, [correct], threshold=90)
    assert suggestion == (correct, 96)


def test_confidence_threshold_can_hide_a_below_threshold_suggestion():
    assert suggest_course_code("ECEI43", ["ECE143"], threshold=97) is None


def test_scanned_pdf_uses_local_ocr_fallback(monkeypatch):
    pdf = fitz.open()
    pdf.new_page()
    raw = pdf.tobytes()
    pdf.close()
    calls = []

    def fake_ocr(image, language, tesseract_path=""):
        calls.append(language)
        return "CS101"

    monkeypatch.setattr(document_parser, "_ocr_image", fake_ocr)
    content = document_parser.extract_document(
        SourceFile(name="scan.pdf", data=raw), AppConfig(ocr_enabled=True, ocr_language="eng")
    )
    assert content.text == "CS101"
    assert content.ocr_used
    assert calls == ["eng"]


def test_scanned_pdf_reports_ocr_failure_without_crashing(monkeypatch):
    pdf = fitz.open()
    pdf.new_page()
    raw = pdf.tobytes()
    pdf.close()

    def fail_ocr(image, language, tesseract_path=""):
        raise RuntimeError("Tesseract missing")

    monkeypatch.setattr(document_parser, "_ocr_image", fail_ocr)
    content = document_parser.extract_document(
        SourceFile(name="scan.pdf", data=raw), AppConfig(ocr_enabled=True)
    )
    assert any("OCR failed" in warning for warning in content.warnings)
