# University Exam Schedule Generator

A local Streamlit app that combines weekly class timetables with the official exam timetable and creates an exam schedule for each level. Documents stay on your computer; the app does not use cloud OCR or external APIs.

## What it does

- Reads class timetable images and PDFs, and an official exam timetable PDF.
- Extracts course codes and matches them to exam dates and times.
- Combines numbered sections by default: `Sophomore 1` and `Sophomore 6` become one `Sophomore` schedule. Different programs, such as `Junior SWE` and `Junior CSE`, stay separate.
- Shows missing courses and possible OCR mistakes so you can correct them before exporting.
- Creates Excel workbooks, a printable PDF, an HTML schedule, and a validation report.

## Install and run

You need Python 3.11 or newer.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown in the terminal, normally <http://127.0.0.1:8501>.
The app is configured to listen only on your computer.

## Use the app

1. Select a folder of weekly class timetables, or upload the timetable files.
2. Select or upload the official exam timetable PDF.
3. Click **Analyze Files**.
4. Review the detected levels, course codes, and exam matches. Edit mistakes, accept or reject OCR suggestions, and add missing exam details if needed.
5. Click **Generate Schedules**. Files are saved to `data/output` by default and can also be downloaded from the page.

Supported timetable files include PNG, JPG/JPEG, PDF, TIFF, BMP, and WebP. Text-based PDFs work without OCR. Scanned documents require Tesseract OCR, installed separately:

- **Windows:** install [Tesseract for Windows](https://github.com/UB-Mannheim/tesseract/wiki). If needed, set its executable path in the app Settings or `config.json`.
- **macOS:** `brew install tesseract`
- **Debian/Ubuntu:** `sudo apt install tesseract-ocr tesseract-ocr-eng`

OCR runs locally. If extraction is uncertain, the app shows a warning rather than silently changing a course code.

## Output files

- `University_Exam_Schedules.xlsx` — summary and a worksheet for each level.
- `ALL_LEVELS.xlsx` — university-wide exam list with levels grouped per course.
- One Excel file per level, plus `University_Exam_Schedules.pdf` and `University_Exam_Schedules.html`.
- `Validation_Report.txt` — missing exams, OCR warnings, unassigned exams, and processing errors.

Change OCR, date/time formats, course-code patterns, section grouping, and output settings in `config.json` or the app Settings.

## Try the included example

Use `examples/sample_input/` as the timetable folder and select `Midterm Exams Schedule - Fall 2026.pdf` as the exam PDF. The expected chronological Freshman schedule is in `examples/sample_freshman5_schedule.csv`; generated sample files are in `examples/sample_output/`.

## Run tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
