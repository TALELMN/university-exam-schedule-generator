"""Text/table extraction with a local OCR fallback."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from exam_scheduler.config import AppConfig
from exam_scheduler.models import SourceFile

LOGGER = logging.getLogger("exam_scheduler")


@dataclass
class DocumentContent:
    text: str = ""
    tables: list[list[list[str]]] = field(default_factory=list)
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)


def _read_source(source: SourceFile) -> bytes:
    if source.data is not None:
        return source.data
    if source.path is None:
        raise ValueError("Source file has no path or uploaded data")
    return source.path.read_bytes()


def _ocr_image(image, language: str, tesseract_path: str = "") -> str:
    try:
        import pytesseract
        from PIL import ImageOps
    except ImportError as exc:
        raise RuntimeError("OCR dependencies are missing. Install pytesseract and Pillow.") from exc
    if tesseract_path.strip():
        pytesseract.pytesseract.tesseract_cmd = tesseract_path.strip()
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    if image.width < 1600:
        scale = min(3, max(2, 1600 // max(1, image.width)))
        image = image.resize((image.width * scale, image.height * scale))
    try:
        # `tesseract_cmd` is configured in extract_document when a custom path is set.
        return pytesseract.image_to_string(image, lang=language, config="--psm 6")
    except Exception as exc:
        raise RuntimeError(f"Tesseract OCR failed: {exc}") from exc


def extract_document(source: SourceFile, config: AppConfig) -> DocumentContent:
    """Read a supported image/PDF and OCR it locally when text extraction is weak."""
    suffix = (source.path.suffix if source.path else Path(source.name).suffix).lower()
    raw = _read_source(source)
    if suffix == ".pdf":
        return _extract_pdf(raw, config)
    if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
        raise ValueError(f"Unsupported document type: {suffix or source.name}")
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(raw))
        text = _ocr_image(image, config.ocr_language, config.tesseract_path) if config.ocr_enabled else ""
        return DocumentContent(text=text, ocr_used=bool(text), warnings=[] if text else ["OCR is disabled or produced no text."])
    except Exception as exc:
        raise RuntimeError(f"Unable to read image or run OCR: {exc}") from exc


def _extract_pdf(raw: bytes, config: AppConfig) -> DocumentContent:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to read PDF files.") from exc
    try:
        document = fitz.open(stream=raw, filetype="pdf")
    except Exception as exc:
        raise RuntimeError(f"Unable to open PDF: {exc}") from exc

    page_texts: list[str] = []
    need_ocr: list[int] = []
    for index, page in enumerate(document):
        text = page.get_text("text") or ""
        page_texts.append(text)
        if len(re.sub(r"\s", "", text)) < 25:
            need_ocr.append(index)

    tables: list[list[list[str]]] = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    cleaned = [[(cell or "").strip() for cell in row] for row in table]
                    if cleaned:
                        tables.append(cleaned)
    except Exception as exc:
        LOGGER.warning("Table extraction failed; continuing with page text: %s", exc)

    warnings: list[str] = []
    did_ocr = False
    if need_ocr and config.ocr_enabled:
        ocr_text: dict[int, str] = {}
        for index in need_ocr:
            try:
                pixmap = document[index].get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
                from PIL import Image
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                ocr_text[index] = _ocr_image(image, config.ocr_language, config.tesseract_path)
                did_ocr = did_ocr or bool(ocr_text[index].strip())
            except Exception as exc:
                warnings.append(f"OCR failed on PDF page {index + 1}: {exc}")
                LOGGER.warning("OCR failed on PDF page %s: %s", index + 1, exc)
        for index, text in ocr_text.items():
            if text.strip():
                page_texts[index] = text
    elif need_ocr:
        warnings.append("Some PDF pages contain no selectable text; OCR is disabled.")

    document.close()
    full_text = "\n".join(text for text in page_texts if text)
    if not full_text.strip() and not warnings:
        warnings.append("No readable text was found in this PDF.")
    return DocumentContent(text=full_text, tables=tables, ocr_used=did_ocr, warnings=warnings)
