# Included example

The provided example models the Freshman 5 input from the project brief. Its
generated schedule is grouped under `Freshman`. It is a
reference fixture (the app's inputs remain PNG/JPG/PDF); see
`sample_exam_records.json` for the exam database and
`sample_freshman5_schedule.csv` for the expected chronologically sorted schedule.
`sample_validation_report.txt` shows the expected clean-run report. The actual
text-based timetable and exam PDFs are under `sample_input/`; rerun
`python examples/create_sample_documents.py` to recreate them if needed.
The tests build a small local text PDF from these same course records and verify
matching, deduplication, and exports without needing OCR or external services.

`sample_output/` contains the generated Excel, PDF, HTML, and validation report
from the included sample PDFs.

For real documents, place the weekly timetable images/PDFs in `data/input/`,
choose that folder in the app, then select the official exam PDF.
