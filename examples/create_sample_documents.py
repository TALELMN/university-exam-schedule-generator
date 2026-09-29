"""Create text-based sample PDFs that can be selected in the local app."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

HERE = Path(__file__).parent
SAMPLE_EXAMS = [
    ("ECO171", "Introduction to Microeconomics", "Saturday, October 11", "08.30-10.30"),
    ("ENG111", "Academic English", "Monday, October 12", "08.30-10.30"),
    ("ECE143", "Digital Systems", "Tuesday, October 13", "13.30-15.30"),
    ("CS101", "Introduction to Programming", "Wednesday, October 14", "11.00-13.00"),
    ("PHYS151", "Classical Mechanics", "Friday, October 16", "13.30-15.30"),
    ("MATH141", "Calculus I", "Saturday, October 17", "08.30-10.30"),
]


def _write_lines(path: Path, title: str, lines: list[str]) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 42), title, fontsize=14)
    y = 72
    for line in lines:
        if y > 780:
            page = document.new_page()
            y = 48
        page.insert_text((48, y), line, fontsize=9)
        y += 18
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()


def main() -> None:
    destination = HERE / "sample_input"
    _write_lines(
        destination / "Freshman 5.pdf", "Freshman 5 Weekly Class Timetable",
        [f"{code} | Weekly timetable entry" for code in ("ECO171", "ENG111", "ECE143", "CS101", "MATH141", "PHYS151", "ECE143")],
    )
    _write_lines(
        destination / "Midterm Exams Schedule - Fall 2026.pdf", "Fall 2026 Midterm Examination Schedule",
        [f"{code} | {name} | Professor: Sample Faculty | {day} | {time}"
         for code, name, day, time in SAMPLE_EXAMS],
    )
    print(f"Created example PDFs in {destination}")


if __name__ == "__main__":
    main()
