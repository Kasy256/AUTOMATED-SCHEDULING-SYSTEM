from datetime import UTC, datetime, timedelta, timezone

from cartlyf_api.feeds.ical import Event, calendar

STAMP = datetime(2027, 1, 1, 12, 0, tzinfo=UTC)


def _event(summary: str, start: datetime | None = None) -> Event:
    start = start or datetime(2027, 1, 11, 6, 0, tzinfo=UTC)
    return Event(
        uid="a1@cartlyf", start=start, end=start + timedelta(hours=1), summary=summary, stamp=STAMP
    )


def _unfold(text: str) -> list[str]:
    return text.replace("\r\n ", "").split("\r\n")


def test_calendar_escapes_and_folds() -> None:
    long = "x" * 200
    text = calendar("Seed lecturer", [_event("A, B; C\nD\\E"), _event(long)])
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")
    for line in text.split("\r\n"):
        assert len(line.encode()) <= 75
    lines = _unfold(text)
    assert "SUMMARY:A\\, B\\; C\\nD\\\\E" in lines
    assert f"SUMMARY:{long}" in lines


def test_calendar_structure_and_utc_times() -> None:
    kampala = timezone(timedelta(hours=3))
    start = datetime(2027, 1, 11, 9, 0, tzinfo=kampala)
    lines = _unfold(calendar("Room, 1", [_event("Maths", start)]))
    assert lines[:4] == [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cartlyf//Schedule//EN",
        "X-WR-CALNAME:Room\\, 1",
    ]
    assert lines[-2:] == ["END:VCALENDAR", ""]
    event = lines[lines.index("BEGIN:VEVENT") : lines.index("END:VEVENT") + 1]
    assert event == [
        "BEGIN:VEVENT",
        "UID:a1@cartlyf",
        "DTSTAMP:20270101T120000Z",
        "DTSTART:20270111T060000Z",
        "DTEND:20270111T070000Z",
        "SUMMARY:Maths",
        "END:VEVENT",
    ]


def test_calendar_without_events_has_no_vevent() -> None:
    assert "BEGIN:VEVENT" not in calendar("Empty", [])


def test_folding_never_splits_a_multibyte_character() -> None:
    summary = "é" * 100
    text = calendar("Café", [_event(summary)])
    for line in text.split("\r\n"):
        assert len(line.encode()) <= 75
    assert f"SUMMARY:{summary}" in _unfold(text)
