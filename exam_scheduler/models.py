"""Typed data structures shared by parsers, matching, and exports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExamRecord:
    code: str
    course_name: str = ""
    professors: list[str] = field(default_factory=list)
    date: str = ""
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    original_date: str = ""
    original_time: str = ""


@dataclass
class LevelTimetable:
    name: str
    source: str
    codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ocr_used: bool = False


@dataclass
class CourseMatch:
    level: str
    code: str
    course_name: str = ""
    professors: str = ""
    date: str = ""
    day: str = ""
    start_time: str = ""
    end_time: str = ""
    status: str = "Missing"
    warning: str = ""


@dataclass
class AnalysisResult:
    levels: list[LevelTimetable] = field(default_factory=list)
    exams: dict[str, ExamRecord] = field(default_factory=dict)
    matches: list[CourseMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    exam_source: str = ""
    ocr_warnings: list[tuple[str, str]] = field(default_factory=list)
    files_attempted: int = 0

    @property
    def source_files_processed(self) -> int:
        return self.files_attempted or len(self.levels) + (1 if self.exam_source else 0)


@dataclass
class SourceFile:
    name: str
    path: Path | None = None
    data: bytes | None = None
