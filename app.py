"""Streamlit entry point for the local University Exam Schedule Generator."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog
except ImportError:  # Some minimal Linux Python builds omit Tk; uploads still work.
    tk = None
    filedialog = None

import pandas as pd
import streamlit as st

from exam_scheduler.config import AppConfig
from exam_scheduler.matching.fuzzy_match import suggest_course_code
from exam_scheduler.matching.matcher import analyze_sources, rebuild_matches, unassigned_exam_codes
from exam_scheduler.matching.normalizer import normalize_code
from exam_scheduler.matching.validator import validation_counts, validation_report
from exam_scheduler.models import ExamRecord, LevelTimetable, SourceFile
from exam_scheduler.output.generate import generate_outputs
from exam_scheduler.parser.timetable_parser import group_level_name
from exam_scheduler.utils.dates import parse_time_range
from exam_scheduler.utils.logging import setup_logging

LOGGER = setup_logging()
SUPPORTED_TIMETABLES = {".png", ".jpg", ".jpeg", ".pdf", ".tif", ".tiff", ".bmp", ".webp"}


def _init_state() -> None:
    if "config" not in st.session_state:
        st.session_state.config = AppConfig.load()
    for key, default in (("timetable_folder", ""), ("exam_path", ""), ("result", None),
                         ("revision", 0), ("generated_files", []),
                         ("timetable_sources", []), ("exam_source", None)):
        if key not in st.session_state:
            st.session_state[key] = default
    st.session_state.setdefault("dismissed_suggestions", set())


def _choose_folder() -> str:
    if tk is None or filedialog is None:
        raise RuntimeError("Tk is not installed. Use the timetable file-upload control instead.")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(title="Select class timetable folder")
    root.destroy()
    return selected


def _choose_pdf() -> str:
    if tk is None or filedialog is None:
        raise RuntimeError("Tk is not installed. Use the PDF upload control instead.")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askopenfilename(
        title="Select official exam timetable PDF",
        filetypes=[("PDF documents", "*.pdf"), ("All files", "*.*")],
    )
    root.destroy()
    return selected


def _folder_sources(folder: str) -> list[SourceFile]:
    if not folder:
        return []
    directory = Path(folder)
    if not directory.is_dir():
        return []
    return [SourceFile(name=item.name, path=item) for item in sorted(directory.iterdir())
            if item.is_file() and item.suffix.lower() in SUPPORTED_TIMETABLES]


def _selected_timetables(*uploaded_groups) -> list[SourceFile]:
    sources = _folder_sources(st.session_state.timetable_folder)
    source_by_name = {item.name.casefold(): index for index, item in enumerate(sources)}
    for uploaded_files in uploaded_groups:
        for item in uploaded_files or []:
            if item.name.lower().endswith(tuple(SUPPORTED_TIMETABLES)):
                replacement = SourceFile(name=item.name, data=item.getvalue())
                key = item.name.casefold()
                if key in source_by_name:
                    sources[source_by_name[key]] = replacement
                else:
                    source_by_name[key] = len(sources)
                    sources.append(replacement)
    return sources


def _as_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _run_analysis(timetables: list[SourceFile], exam: SourceFile, config: AppConfig) -> None:
    with st.spinner("Reading files locally and matching course codes…"):
        result = analyze_sources(timetables, exam, config)
    st.session_state.result = result
    st.session_state.timetable_sources = timetables
    st.session_state.exam_source = exam
    st.session_state.generated_files = []
    st.session_state.revision += 1


def _invalidate_outputs() -> None:
    st.session_state.generated_files = []


def _show_suggestions(result, config: AppConfig) -> None:
    all_exam_codes = list(result.exams)
    timetable_codes = list(dict.fromkeys(code for level in result.levels for code in level.codes))
    suggestions = []
    for level in result.levels:
        for code in level.codes:
            threshold = max(config.fuzzy_match_threshold, config.ocr_confidence_threshold)
            suggestion = suggest_course_code(code, all_exam_codes, threshold)
            if suggestion and suggestion[0] != code:
                suggestions.append((level.name, "timetable", level, code, suggestion[0], suggestion[1]))
    for code in all_exam_codes:
        threshold = max(config.fuzzy_match_threshold, config.ocr_confidence_threshold)
        suggestion = suggest_course_code(code, timetable_codes, threshold)
        if suggestion and suggestion[0] != code:
            suggestions.append(("Exam timetable", "exam", None, code, suggestion[0], suggestion[1]))
    dismissed = st.session_state.dismissed_suggestions
    suggestions = [item for item in suggestions if (item[0], item[3]) not in dismissed]
    if not suggestions:
        return
    st.markdown("#### Possible OCR course-code issues")
    st.caption("Suggestions are never applied automatically. Accept only after checking the source timetable.")
    for index, (owner, kind, level, detected, candidate, confidence) in enumerate(suggestions):
        left, right, reject_col = st.columns([6, 1.2, 1.2])
        left.warning(f'**{owner}** — detected `{detected}`; possible match `{candidate}` ({confidence}% confidence)')
        with right:
            if st.button("Accept", key=f"accept_{st.session_state.revision}_{index}"):
                if kind == "timetable":
                    level.codes = [candidate if item == detected else item for item in level.codes]
                    level.warnings = [warning for warning in level.warnings if detected not in warning]
                else:
                    record = result.exams.pop(detected)
                    record.code = candidate
                    existing = result.exams.get(candidate)
                    if existing:
                        for field in ("course_name", "date", "day", "start_time", "end_time",
                                      "original_date", "original_time"):
                            if not getattr(existing, field) and getattr(record, field):
                                setattr(existing, field, getattr(record, field))
                        existing.professors = list(dict.fromkeys(existing.professors + record.professors))
                    else:
                        result.exams[candidate] = record
                result.warnings = [warning for warning in result.warnings if detected not in warning]
                rebuild_matches(result)
                _invalidate_outputs()
                st.session_state.revision += 1
                st.rerun()
        with reject_col:
            if st.button("Reject", key=f"reject_{st.session_state.revision}_{index}"):
                dismissed.add((owner, detected))
                st.session_state.revision += 1
                st.rerun()


def _review_levels(result, config: AppConfig) -> None:
    st.markdown("#### Correct detected level names")
    level_frame = pd.DataFrame([
        {"Source file": level.source, "Detected level": level.name, "Level name to use": level.name}
        for level in result.levels
    ], columns=["Source file", "Detected level", "Level name to use"])
    edited_levels = st.data_editor(
        level_frame, key=f"level_names_{st.session_state.revision}", hide_index=True,
        use_container_width=True, num_rows="fixed",
        column_config={"Source file": st.column_config.TextColumn(disabled=True),
                       "Detected level": st.column_config.TextColumn(disabled=True)},
    )
    if st.button("Apply level names", key=f"apply_levels_{st.session_state.revision}"):
        rename = {}
        used_names = set()
        for _, row in edited_levels.iterrows():
            old, new = _as_text(row["Detected level"]), _as_text(row["Level name to use"])
            if old and new:
                if config.group_numbered_sections:
                    new = group_level_name(new)
                base, suffix = new, 2
                while new in used_names:
                    new = f"{base} ({suffix})"
                    suffix += 1
                used_names.add(new)
                rename[old] = new
        for level in result.levels:
            level.name = rename.get(level.name, level.name)
        _invalidate_outputs()
        rebuild_matches(result)
        st.session_state.revision += 1
        st.success("Level names updated.")
        st.rerun()


def _review_course_codes(result, config: AppConfig) -> None:
    st.markdown("#### Review / edit timetable course codes")
    rows = [{"Level": level.name, "Course Code": code}
            for level in result.levels for code in level.codes]
    frame = pd.DataFrame(rows, columns=["Level", "Course Code"])
    st.caption("Edit a code, remove a row, or add rows to assign courses manually. Duplicate codes within a level are deduplicated.")
    edited = st.data_editor(
        frame, key=f"courses_{st.session_state.revision}", hide_index=True,
        use_container_width=True, num_rows="dynamic",
        column_config={"Level": st.column_config.TextColumn("Level", required=True),
                       "Course Code": st.column_config.TextColumn("Course Code", required=True)},
    )
    if st.button("Apply course-code changes", key=f"apply_courses_{st.session_state.revision}"):
        levels_by_name = {level.name: level for level in result.levels}
        for level in result.levels:
            level.codes = []
        for _, row in edited.iterrows():
            name, code = _as_text(row.get("Level")), normalize_code(_as_text(row.get("Course Code")))
            if config.group_numbered_sections:
                name = group_level_name(name)
            if not name or not code:
                continue
            if name not in levels_by_name:
                levels_by_name[name] = LevelTimetable(name=name, source="Manually added")
                result.levels.append(levels_by_name[name])
            levels_by_name[name].codes.append(code)
        for level in result.levels:
            level.warnings = [warning for warning in level.warnings
                              if not any(f'"{code}"' in warning for code in level.codes)]
        active_codes = {code for level in result.levels for code in level.codes}
        result.warnings = [warning for warning in result.warnings
                           if "Suspicious OCR course code" not in warning
                           or any(f'"{code}"' in warning for code in active_codes)]
        _invalidate_outputs()
        rebuild_matches(result)
        st.session_state.revision += 1
        st.success("Course codes updated; matches were recomputed without re-reading documents.")
        st.rerun()


def _review_exam_records(result) -> None:
    st.markdown("#### Correct exam timetable records")
    rows = []
    for code, exam in result.exams.items():
        rows.append({
            "Course Code": code, "Course Name": exam.course_name,
            "Professor(s)": "; ".join(exam.professors), "Date (YYYY-MM-DD)": exam.date,
            "Day": exam.day, "Start Time": exam.start_time, "End Time": exam.end_time,
            "Original Date": exam.original_date, "Original Time": exam.original_time,
        })
    columns = ["Course Code", "Course Name", "Professor(s)", "Date (YYYY-MM-DD)", "Day",
               "Start Time", "End Time", "Original Date", "Original Time"]
    edited = st.data_editor(
        pd.DataFrame(rows, columns=columns), key=f"exam_records_{st.session_state.revision}",
        hide_index=True, use_container_width=True, num_rows="dynamic",
    )
    if st.button("Apply exam-record changes", key=f"apply_exam_{st.session_state.revision}"):
        exams = {}
        invalid_dates = []
        for _, row in edited.iterrows():
            code = normalize_code(_as_text(row.get("Course Code")))
            if not code:
                continue
            date_value = _as_text(row.get("Date (YYYY-MM-DD)"))
            day = _as_text(row.get("Day"))
            if date_value:
                try:
                    day = dt.date.fromisoformat(date_value).strftime("%A") if not day else day
                except ValueError:
                    invalid_dates.append(code)
                    continue
            professors = [part.strip() for part in re_split_professors(_as_text(row.get("Professor(s)"))) if part.strip()]
            exams[code] = ExamRecord(
                code=code, course_name=_as_text(row.get("Course Name")), professors=professors,
                date=date_value, day=day, start_time=_as_text(row.get("Start Time")),
                end_time=_as_text(row.get("End Time")), original_date=_as_text(row.get("Original Date")),
                original_time=_as_text(row.get("Original Time")),
            )
        if invalid_dates:
            st.error("Correct invalid YYYY-MM-DD dates before applying changes: " + ", ".join(invalid_dates))
            return
        result.exams = exams
        rebuild_matches(result)
        _invalidate_outputs()
        st.session_state.revision += 1
        st.success("Exam records updated and all matches recomputed.")
        st.rerun()


def re_split_professors(value: str) -> list[str]:
    import re
    return re.split(r"[;,]", value)


def _manual_exam_form(result) -> None:
    with st.expander("Manually assign or add an exam record"):
        levels = [level.name for level in result.levels]
        with st.form("manual_exam_form"):
            level = st.selectbox("Assign to level", levels or [""], disabled=not levels)
            code = st.text_input("Course code")
            course_name = st.text_input("Course name")
            exam_date = st.text_input("Exam date (YYYY-MM-DD)", placeholder="2026-10-14")
            col1, col2 = st.columns(2)
            start_time = col1.text_input("Start time (HH:MM)", placeholder="08:30")
            end_time = col2.text_input("End time (HH:MM)", placeholder="10:30")
            professors = st.text_input("Professor(s), optional")
            submitted = st.form_submit_button("Save exam and assign course")
        if submitted:
            normalized = normalize_code(code)
            try:
                parsed = dt.date.fromisoformat(exam_date)
            except ValueError:
                parsed = None
            parsed_times = parse_time_range(f"{start_time}-{end_time}")
            if not normalized or not parsed or not parsed_times:
                st.error("Enter a course code, a valid YYYY-MM-DD date, and start/end times in HH:MM format.")
            else:
                result.exams[normalized] = ExamRecord(
                    code=normalized, course_name=course_name.strip(),
                    professors=[part.strip() for part in re_split_professors(professors) if part.strip()],
                    date=parsed.isoformat(), day=parsed.strftime("%A"),
                    start_time=parsed_times[0], end_time=parsed_times[1],
                    original_date=parsed.strftime("%A, %B %d, %Y"),
                    original_time=f"{start_time.strip()}-{end_time.strip()}",
                )
                if level:
                    level_record = next(item for item in result.levels if item.name == level)
                    level_record.codes.append(normalized)
                rebuild_matches(result)
                _invalidate_outputs()
                st.session_state.revision += 1
                st.success(f"Saved {normalized} and updated matching.")
                st.rerun()


def _show_review(result, config: AppConfig) -> None:
    counts = validation_counts(result)
    st.subheader("Analysis summary")
    columns = st.columns(5)
    for column, (label, key) in zip(columns, [("Levels", "levels_detected"), ("Unique courses", "unique_courses"),
                                               ("Exam records", "exam_records"), ("Matched", "successfully_matched"),
                                               ("Missing", "missing_exam_information")]):
        column.metric(label, counts[key])
    st.caption(f"Warnings: {len(result.warnings) + len(result.errors)} · OCR warnings: {counts['ocr_warnings']}")
    if result.errors:
        with st.expander(f"Files that could not be processed ({len(result.errors)})", expanded=True):
            for error in result.errors:
                st.error(f"Failed to process: {error}\n\nThis file was skipped; other files continued. Upload a replacement or retry OCR and analyze again.")
            if st.button("Retry OCR for selected files", key="retry_ocr"):
                config.ocr_enabled = True
                _run_analysis(st.session_state.timetable_sources, st.session_state.exam_source, config)
                st.rerun()
    if result.warnings:
        with st.expander(f"Extraction warnings ({len(result.warnings)})"):
            for warning in result.warnings:
                st.warning(warning)
            if any(any(marker in warning for marker in (
                    "OCR failed", "OCR is disabled", "No readable text", "No course codes", "No exam course rows"
            )) for warning in result.warnings):
                if st.button("Retry OCR", key="retry_ocr_warning"):
                    config.ocr_enabled = True
                    _run_analysis(st.session_state.timetable_sources, st.session_state.exam_source, config)
                    st.rerun()

    _show_suggestions(result, config)
    with st.expander("Edit detected level names", expanded=False):
        _review_levels(result, config)
    with st.expander("Review timetable courses", expanded=True):
        _review_course_codes(result, config)
    with st.expander("Review / correct official exam records", expanded=False):
        _review_exam_records(result)
        _manual_exam_form(result)

    st.subheader("Review matches")
    level_options = ["All levels"] + [level.name for level in result.levels]
    selected_level = st.selectbox("Filter by level", level_options, key=f"filter_level_{st.session_state.revision}")
    selected_status = st.multiselect("Filter by status", ["Matched", "Missing", "Needs review", "Warnings"],
                                     default=["Matched", "Missing", "Needs review", "Warnings"],
                                     key=f"filter_status_{st.session_state.revision}")
    warning_levels = {level.name for level in result.levels if level.warnings}
    warning_levels.update(level for level, _ in result.ocr_warnings)
    filtered = [row for row in result.matches
                if (selected_level == "All levels" or row.level == selected_level)
                and (row.status in selected_status or
                     ("Warnings" in selected_status and (bool(row.warning) or row.level in warning_levels)))]
    match_frame = pd.DataFrame([{
        "Level": row.level, "Course Code": row.code, "Course Name": row.course_name or ("Unknown" if row.status == "Missing" else ""),
        "Exam Date": row.date or "—", "Day": row.day or "—",
        "Exam Time": f"{row.start_time}-{row.end_time}" if row.start_time and row.end_time else "—",
        "Status": row.status,
    } for row in filtered])
    st.dataframe(match_frame, use_container_width=True, hide_index=True)

    extras = unassigned_exam_codes(result)
    if extras:
        with st.expander(f"Exam found but not assigned to a timetable ({len(extras)})"):
            for code in extras:
                exam = result.exams[code]
                st.info(f"**{code}** — {exam.course_name or 'Unknown'}")
    missing_count = sum(row.status == "Missing" for row in result.matches)
    if missing_count:
        st.warning(
            "Missing exam information is retained in exports. Possible reasons: the course has no exam, "
            "an OCR error, a course-code mismatch, or an incomplete exam PDF. Add an exam record above "
            "or correct the source code before generating."
        )

    st.subheader("Generate schedules")
    output_dir = st.text_input("Output folder", value=config.output_directory, key="output_directory_input")
    if st.button("Generate Schedules", type="primary", key="generate_schedules"):
        try:
            files = generate_outputs(result, output_dir, config)
            st.session_state.generated_files = files
            st.success(f"Created {len(files)} output files in `{Path(output_dir).resolve()}`")
        except Exception as exc:
            LOGGER.exception("Output generation failed")
            st.error(f"Could not generate output files: {exc}")
    if st.session_state.generated_files:
        st.markdown("#### Download generated files")
        for path in st.session_state.generated_files:
            try:
                st.download_button(
                    f"Download {path.name}", data=path.read_bytes(), file_name=path.name,
                    mime=_mime_type(path.suffix), key=f"download_{path.name}_{st.session_state.revision}",
                )
            except OSError as exc:
                st.error(f"Cannot read {path}: {exc}")
    with st.expander("Validation report"):
        st.code(validation_report(result), language="text")


def _mime_type(suffix: str) -> str:
    return {".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pdf": "application/pdf", ".html": "text/html", ".txt": "text/plain"}.get(suffix, "application/octet-stream")


def main() -> None:
    st.set_page_config(page_title="University Exam Schedule Generator", page_icon="📅", layout="wide")
    _init_state()
    config: AppConfig = st.session_state.config

    st.title("University Exam Schedule Generator")
    st.caption("Generate per-level exam schedules locally from weekly timetables and the official exam PDF.")
    st.info("Your documents are processed on this computer. No files are sent to an external service.")

    with st.sidebar:
        st.header("Settings")
        config.ocr_enabled = st.checkbox("Enable local OCR fallback", value=config.ocr_enabled)
        config.ocr_language = st.text_input("OCR language", value=config.ocr_language, help="Tesseract language code, usually eng")
        config.tesseract_path = st.text_input("Tesseract executable path (optional)", value=config.tesseract_path,
                                              placeholder="Leave blank when tesseract is on PATH")
        config.group_numbered_sections = st.checkbox(
            "Combine numbered sections by level", value=config.group_numbered_sections,
            help="For example, merge Sophomore 1 and Sophomore 6 into one Sophomore schedule.",
        )
        config.ocr_confidence_threshold = st.slider("OCR correction confidence threshold", 50, 100,
                                                    int(config.ocr_confidence_threshold))
        config.fuzzy_match_threshold = st.slider("Fuzzy suggestion threshold", 50, 100,
                                                 int(config.fuzzy_match_threshold))
        config.exam_year = st.number_input("Default exam year", min_value=2000, max_value=2100,
                                           value=int(config.exam_year), step=1)
        config.generate_excel = st.checkbox("Generate Excel", value=config.generate_excel)
        config.generate_pdf = st.checkbox("Generate PDF", value=config.generate_pdf)
        config.generate_html = st.checkbox("Generate HTML", value=config.generate_html)
        st.caption("OCR requires the Tesseract application installed on this computer.")

    st.subheader("1. Class timetable folder")
    folder_col, folder_text_col = st.columns([1, 4])
    if folder_col.button("Select Folder…", key="select_folder"):
        try:
            selected = _choose_folder()
            if selected:
                st.session_state.timetable_folder = selected
        except Exception as exc:
            st.warning(f"Native folder picker unavailable: {exc}. Use the file upload control below.")
    folder_text_col.text_input("Selected folder", key="timetable_folder", placeholder="Choose a local folder")
    browser_folder_files = st.file_uploader(
        "Or select a timetable folder in the browser", type=["png", "jpg", "jpeg", "pdf", "tif", "tiff", "bmp", "webp"],
        accept_multiple_files="directory", key="timetable_directory_upload",
        help="Folder contents are sent only to this local Streamlit app.",
    )
    uploaded_timetables = st.file_uploader(
        "Or select individual timetable files (PNG, JPG, PDF, scanned PDF)",
        type=["png", "jpg", "jpeg", "pdf", "tif", "tiff", "bmp", "webp"],
        accept_multiple_files=True, key="timetable_uploads",
    )
    timetables = _selected_timetables(browser_folder_files, uploaded_timetables)
    st.caption(f"Detected {len(timetables)} timetable file(s) from folder and uploads.")
    if timetables:
        st.write("Timetable files: " + ", ".join(source.name for source in timetables))

    st.subheader("2. Official exam timetable PDF")
    pdf_col, pdf_text_col = st.columns([1, 4])
    if pdf_col.button("Select PDF…", key="select_exam_pdf"):
        try:
            selected = _choose_pdf()
            if selected:
                st.session_state.exam_path = selected
        except Exception as exc:
            st.warning(f"Native file picker unavailable: {exc}. Use the PDF upload control below.")
    pdf_text_col.text_input("Selected PDF", key="exam_path", placeholder="Choose official exam schedule PDF")
    uploaded_exam = st.file_uploader("Or upload the exam timetable PDF", type=["pdf"], key="exam_upload")
    if st.session_state.exam_path:
        st.caption(f"Selected: {Path(st.session_state.exam_path).name}")
    elif uploaded_exam:
        st.caption(f"Selected upload: {uploaded_exam.name}")

    exam_source = None
    if st.session_state.exam_path:
        path = Path(st.session_state.exam_path)
        if path.is_file() and path.suffix.lower() == ".pdf":
            exam_source = SourceFile(name=path.name, path=path)
        else:
            st.warning("The selected exam path is not a readable PDF file.")
    elif uploaded_exam:
        exam_source = SourceFile(name=uploaded_exam.name, data=uploaded_exam.getvalue())

    if st.button("Analyze Files", type="primary", disabled=not timetables or exam_source is None):
        _run_analysis(timetables, exam_source, config)

    if st.session_state.result is not None:
        st.divider()
        _show_review(st.session_state.result, config)


if __name__ == "__main__":
    main()
