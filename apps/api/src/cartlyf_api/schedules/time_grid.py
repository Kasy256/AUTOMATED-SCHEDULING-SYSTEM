"""Wall-clock calendars → UTC instants. Everything DST-sensitive lives here."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

MINUTES_PER_DAY = 1440
Interval = tuple[datetime, datetime]
_MINUTE = timedelta(minutes=1)


def local_instant(day: date, minute: int, tz: ZoneInfo) -> datetime:
    """UTC instant of wall-clock `minute` (0..1440) on `day`. A time inside a DST gap uses the
    pre-transition offset and an ambiguous time its first occurrence (fold=0)."""
    day += timedelta(days=minute // MINUTES_PER_DAY)
    minute %= MINUTES_PER_DAY
    return datetime.combine(day, time(minute // 60, minute % 60), tzinfo=tz).astimezone(UTC)


@dataclass(frozen=True)
class Horizon:
    """Local dates first_day..last_day (inclusive) of a schedule, in its timezone."""

    first_day: date
    last_day: date
    timezone: ZoneInfo

    @property
    def start(self) -> datetime:
        return local_instant(self.first_day, 0, self.timezone)

    @property
    def end(self) -> datetime:
        return local_instant(self.last_day, MINUTES_PER_DAY, self.timezone)

    def days(self) -> list[date]:
        count = (self.last_day - self.first_day).days + 1
        return [self.first_day + timedelta(days=n) for n in range(count)]


def horizon_for(start_date: date, end_date: date, timezone: str) -> Horizon:
    return Horizon(start_date, end_date, ZoneInfo(timezone))


def extend_to(horizon: Horizon, instant: datetime) -> Horizon:
    """The same horizon with whole local days added until it reaches `instant`."""
    last = horizon.last_day
    while local_instant(last, MINUTES_PER_DAY, horizon.timezone) < instant:
        last += timedelta(days=1)
    return Horizon(horizon.first_day, last, horizon.timezone)


def day_windows(horizon: Horizon) -> list[Interval]:
    return part_windows(horizon, 0, MINUTES_PER_DAY)


def part_windows(horizon: Horizon, start_minute: int, end_minute: int) -> list[Interval]:
    tz = horizon.timezone
    return [
        (local_instant(day, start_minute, tz), local_instant(day, end_minute, tz))
        for day in horizon.days()
    ]


def week_windows(horizon: Horizon) -> list[Interval]:
    """Local Monday-to-Sunday weeks, clipped to the horizon."""
    tz = horizon.timezone
    windows: list[Interval] = []
    for day in horizon.days():
        if day == horizon.first_day or day.weekday() == 0:
            sunday = day + timedelta(days=6 - day.weekday())
            last = min(sunday, horizon.last_day)
            windows.append((local_instant(day, 0, tz), local_instant(last, MINUTES_PER_DAY, tz)))
    return windows


def floor_minutes(origin: datetime, instant: datetime) -> int:
    return (instant - origin) // _MINUTE


def ceil_minutes(origin: datetime, instant: datetime) -> int:
    return -((origin - instant) // _MINUTE)
