"""Date and time parsing helpers for the common formats in exam schedules."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime


MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})
MONTH_PATTERN = "|".join(sorted({name for name in MONTHS}, key=len, reverse=True))
WEEKDAYS = {name.lower(): name for name in calendar.day_name}
TIME_RANGE_RE = re.compile(
    r"(?<![\d:.])(\d{1,2})[.:](\d{2})\s*(am|pm)?\s*[-–—to]+\s*"
    r"(\d{1,2})[.:](\d{2})\s*(am|pm)?(?!\d)", re.IGNORECASE
)


def parse_date(value: str, default_year: int = 2026,
               date_formats: list[str] | None = None) -> tuple[str, str] | None:
    """Return ISO date and weekday; accept named and numeric dates."""
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", value.strip(), flags=re.I)
    text = re.sub(r"\s+", " ", text)
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else default_year
    stated_day = re.search(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", text, re.I)

    # Honor configured exact formats before applying the flexible named/numeric parsers.
    weekday_free = re.sub(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b[,]?\s*", "", text, flags=re.I)
    format_inputs = [text, weekday_free, weekday_free.replace(",", "").strip()]
    for date_format in date_formats or []:
        for candidate in format_inputs:
            candidate_format = date_format
            if "%Y" not in date_format and "%y" not in date_format:
                candidate = f"{candidate} {year}"
                candidate_format = f"{date_format} %Y"
            try:
                parsed_datetime = datetime.strptime(candidate, candidate_format)
            except ValueError:
                continue
            parsed_year = parsed_datetime.year if "%Y" in date_format or "%y" in date_format else year
            parsed = date(parsed_year, parsed_datetime.month, parsed_datetime.day)
            day_name = WEEKDAYS[stated_day.group(1).lower()] if stated_day else parsed.strftime("%A")
            return parsed.isoformat(), day_name

    # Named dates such as "Wednesday, October 14th" or "14 Oct 2026".
    month_re = re.compile(rf"\b({MONTH_PATTERN})\b", re.IGNORECASE)
    match = month_re.search(text)
    try:
        if match:
            month = MONTHS[match.group(1).lower()]
            before = text[:match.start()]
            after = text[match.end():]
            after_candidates = [int(item) for item in re.findall(r"\b(\d{1,2})\b", after)]
            before_candidates = [int(item) for item in re.findall(r"\b(\d{1,2})\b", before)]
            day_candidates = [item for item in after_candidates if 1 <= item <= 31]
            if not day_candidates:
                day_candidates = [item for item in before_candidates if 1 <= item <= 31]
            day_number = day_candidates[0] if day_candidates else 0
            if not day_number:
                return None
            parsed = date(year, month, day_number)
            day_name = WEEKDAYS[stated_day.group(1).lower()] if stated_day else parsed.strftime("%A")
            return parsed.isoformat(), day_name

        iso = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
        if iso:
            parsed = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
            day_name = WEEKDAYS[stated_day.group(1).lower()] if stated_day else parsed.strftime("%A")
            return parsed.isoformat(), day_name

        numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", text)
        if numeric:
            first, second = int(numeric.group(1)), int(numeric.group(2))
            parsed_year = int(numeric.group(3)) if numeric.group(3) else year
            # Date formats such as 10/14 are interpreted as month/day where possible.
            month, day_number = (first, second) if first <= 12 else (second, first)
            parsed = date(parsed_year, month, day_number)
            day_name = WEEKDAYS[stated_day.group(1).lower()] if stated_day else parsed.strftime("%A")
            return parsed.isoformat(), day_name
    except ValueError:
        return None
    return None


def parse_time_range(value: str, time_formats: list[str] | None = None) -> tuple[str, str] | None:
    """Parse time ranges including 13.30-15.30 and 8:30 AM - 10:30 AM."""
    text = value.replace("to", "-")
    match = TIME_RANGE_RE.search(text)
    if not match:
        generic = re.search(
            r"(?P<start>\d{1,2}[.:]\d{2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:[-–—]|\bto\b)\s*"
            r"(?P<end>\d{1,2}[.:]\d{2}(?::\d{2})?\s*(?:am|pm)?)", text, re.I
        )
        if not generic:
            return None
        parsed_times = []
        for endpoint in (generic.group("start"), generic.group("end")):
            parsed = None
            for time_format in time_formats or []:
                try:
                    parsed = datetime.strptime(endpoint.strip(), time_format).strftime("%H:%M")
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None
            parsed_times.append(parsed)
        return parsed_times[0], parsed_times[1]
    h1, m1, meridiem1, h2, m2, meridiem2 = match.groups()

    def normalize(hour: str, minute: str, meridiem: str | None) -> str | None:
        h, m = int(hour), int(minute)
        if m > 59 or h > 23:
            return None
        if meridiem:
            suffix = meridiem.lower()
            if h < 1 or h > 12:
                return None
            h = h % 12 + (12 if suffix == "pm" else 0)
        return f"{h:02d}:{m:02d}"

    # If only one endpoint has AM/PM, apply it to both endpoints.
    meridiem1 = meridiem1 or meridiem2
    meridiem2 = meridiem2 or meridiem1
    start, end = normalize(h1, m1, meridiem1), normalize(h2, m2, meridiem2)
    return (start, end) if start and end else None


def display_date(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d")
    except (ValueError, TypeError):
        return value or "—"
