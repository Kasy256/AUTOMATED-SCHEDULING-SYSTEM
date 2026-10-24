"""Minimal RFC 5545 writer for read-only schedule feeds."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

_MAX_OCTETS = 75


@dataclass(frozen=True)
class Event:
    uid: str
    start: datetime
    end: datetime
    summary: str
    stamp: datetime


def _text(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return escaped.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> list[str]:
    """Split at 75 UTF-8 octets on character boundaries; continuations start with a space."""
    parts: list[str] = []
    current, size = "", 0
    for char in line:
        width = len(char.encode())
        if size + width > _MAX_OCTETS:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return parts


def calendar(name: str, events: Sequence[Event]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cartlyf//Schedule//EN",
        f"X-WR-CALNAME:{_text(name)}",
    ]
    for event in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_text(event.uid)}",
            f"DTSTAMP:{_utc(event.stamp)}",
            f"DTSTART:{_utc(event.start)}",
            f"DTEND:{_utc(event.end)}",
            f"SUMMARY:{_text(event.summary)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "".join(f"{part}\r\n" for line in lines for part in _fold(line))
