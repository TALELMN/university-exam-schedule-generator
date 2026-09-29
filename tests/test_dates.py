from exam_scheduler.utils.dates import parse_date, parse_time_range


def test_named_exam_dates_preserve_published_weekday_and_default_year():
    assert parse_date("Saturday, October 11th", 2026) == ("2026-10-11", "Saturday")
    assert parse_date("Wednesday, October 14, 2026", 2025) == ("2026-10-14", "Wednesday")
    assert parse_date("14 October 2026", 2025) == ("2026-10-14", "Wednesday")
    assert parse_date("2026/10/14", 2025, ["%Y/%m/%d"]) == ("2026-10-14", "Wednesday")
    assert parse_date("14.10.2026", 2025, ["%d.%m.%Y"]) == ("2026-10-14", "Wednesday")


def test_time_ranges_normalize_dot_and_colon_formats():
    assert parse_time_range("13.30-15.30") == ("13:30", "15:30")
    assert parse_time_range("8:30 AM - 10:30 AM") == ("08:30", "10:30")
    assert parse_time_range("08:30:00 - 10:30:00", ["%H:%M:%S"]) == ("08:30", "10:30")
