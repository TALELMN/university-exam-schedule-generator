"""Application configuration loading and defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppConfig:
    course_code_pattern: str = r"[A-Z]{2,5}\s?[0-9]{3,4}"
    suspicious_course_code_pattern: str = r"[A-Z]{2,5}\s?[A-Z0-9IO]{3,4}"
    ocr_confidence_threshold: int = 90
    fuzzy_match_threshold: int = 88
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    tesseract_path: str = ""
    date_formats: list[str] = field(default_factory=lambda: [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y", "%B %d", "%b %d"
    ])
    time_formats: list[str] = field(default_factory=lambda: ["%H:%M", "%H.%M", "%I:%M %p", "%I.%M %p"])
    exam_year: int = 2026
    group_numbered_sections: bool = True
    output_directory: str = "data/output"
    generate_excel: bool = True
    generate_pdf: bool = True
    generate_html: bool = True

    @classmethod
    def load(cls, path: str | Path = "config.json") -> "AppConfig":
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with config_path.open("r", encoding="utf-8") as handle:
            values: dict[str, Any] = json.load(handle)
        known = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in values.items() if key in known})
