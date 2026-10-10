from datetime import UTC, date, datetime, timedelta

from cartlyf_api.schedules.time_grid import (
    ceil_minutes,
    day_windows,
    extend_to,
    floor_minutes,
    horizon_for,
    local_instant,
    part_windows,
    week_windows,
)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def hours(window: tuple[datetime, datetime]) -> float:
    return (window[1] - window[0]) / timedelta(hours=1)


def test_kampala_horizon_is_utc_plus_three() -> None:
    h = horizon_for(date(2027, 1, 11), date(2027, 1, 15), "Africa/Kampala")
    assert h.start == utc(2027, 1, 10, 21) and h.end == utc(2027, 1, 15, 21)
    assert [hours(w) for w in day_windows(h)] == [24.0] * 5


def test_london_days_are_23_and_25_hours_across_dst() -> None:
    spring = horizon_for(date(2026, 3, 27), date(2026, 3, 30), "Europe/London")
    assert [hours(w) for w in day_windows(spring)] == [24.0, 24.0, 23.0, 24.0]
    autumn = horizon_for(date(2026, 10, 24), date(2026, 10, 26), "Europe/London")
    assert [hours(w) for w in day_windows(autumn)] == [24.0, 25.0, 24.0]


def test_local_instant_handles_midnight_and_gap() -> None:
    london = horizon_for(date(2026, 3, 29), date(2026, 3, 29), "Europe/London").timezone
    assert local_instant(date(2026, 3, 28), 1440, london) == utc(2026, 3, 29, 0)
    # 01:30 does not exist on 29 March in London; fold=0 maps it with the GMT offset.
    assert local_instant(date(2026, 3, 29), 90, london) == utc(2026, 3, 29, 1, 30)


def test_week_windows_follow_local_mondays_and_clip_to_horizon() -> None:
    h = horizon_for(date(2027, 1, 13), date(2027, 1, 26), "Africa/Kampala")  # Wed .. Tue
    weeks = week_windows(h)
    assert [w[0] for w in weeks] == [
        utc(2027, 1, 12, 21),
        utc(2027, 1, 17, 21),
        utc(2027, 1, 24, 21),
    ]
    assert weeks[-1][1] == h.end


def test_part_windows_and_minutes() -> None:
    h = horizon_for(date(2027, 1, 11), date(2027, 1, 12), "Africa/Kampala")
    mornings = part_windows(h, 480, 780)
    assert mornings[0] == (utc(2027, 1, 11, 5), utc(2027, 1, 11, 10))
    assert floor_minutes(h.start, utc(2027, 1, 11, 5, 0, 59)) == 480
    assert ceil_minutes(h.start, utc(2027, 1, 11, 5, 0, 1)) == 481


def test_extend_to_covers_an_overnight_tail() -> None:
    h = horizon_for(date(2027, 1, 11), date(2027, 1, 11), "Africa/Kampala")
    longer = extend_to(h, h.end + timedelta(hours=7))
    assert longer.last_day == date(2027, 1, 12) and longer.first_day == h.first_day
