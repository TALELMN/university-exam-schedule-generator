"""One-call output generation used by the UI and command-line example."""

from __future__ import annotations

from pathlib import Path

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.validator import validation_report
from exam_scheduler.models import AnalysisResult
from exam_scheduler.output.common import export_directory
from exam_scheduler.output.excel import generate_schedule_workbook
from exam_scheduler.output.html import generate_html
from exam_scheduler.output.pdf import generate_pdf


def generate_outputs(result: AnalysisResult, output_dir: str | Path,
                     config: AppConfig) -> list[Path]:
    directory = export_directory(output_dir)
    files: list[Path] = []
    if config.generate_excel:
        files.extend(generate_schedule_workbook(result, directory))
    if config.generate_pdf:
        files.append(generate_pdf(result, directory))
    if config.generate_html:
        files.append(generate_html(result, directory))
    report = directory / "Validation_Report.txt"
    report.write_text(validation_report(result), encoding="utf-8")
    files.append(report)
    return files
