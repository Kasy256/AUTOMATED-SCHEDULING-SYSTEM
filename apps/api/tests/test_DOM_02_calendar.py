from datetime import UTC, date, datetime

from cartlyf_api.resources.calendar import DatedException, WeeklyRule, expand_calendar
from cartlyf_api.schedules.time_grid import horizon_for


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


KAMPALA = horizon_for(date(2027, 1, 11), date(2027, 1, 12), "Africa/Kampala")  # Mon, Tue
MON_9_TO_5 = WeeklyRule("available", 0, 8 * 60, 17 * 60)


def test_DOM_02_kampala_available_rule_blocks_everything_else() -> None:
    windows = expand_calendar([MON_9_TO_5], [], KAMPALA)
    assert windows.unavailable == [
        (utc(2027, 1, 10, 21), utc(2027, 1, 11, 5)),
        (utc(2027, 1, 11, 14), utc(2027, 1, 12, 21)),
    ]


def test_DOM_02_no_available_rules_means_always_available() -> None:
    lunch = WeeklyRule("unavailable", 1, 12 * 60, 13 * 60)
    assert expand_calendar([lunch], [], KAMPALA).unavailable == [
        (utc(2027, 1, 12, 9), utc(2027, 1, 12, 10))
    ]


def test_DOM_02_exceptions_override_weekly_rules() -> None:
    meeting = DatedException("unavailable", utc(2027, 1, 11, 9), utc(2027, 1, 11, 10))
    overtime = DatedException("available", utc(2027, 1, 11, 14), utc(2027, 1, 11, 16))
    windows = expand_calendar([MON_9_TO_5], [meeting, overtime], KAMPALA)
    assert windows.unavailable == [
        (utc(2027, 1, 10, 21), utc(2027, 1, 11, 5)),
        (utc(2027, 1, 11, 9), utc(2027, 1, 11, 10)),
        (utc(2027, 1, 11, 16), utc(2027, 1, 12, 21)),
    ]


def test_DOM_02_london_rule_keeps_wall_clock_across_spring_forward() -> None:
    horizon = horizon_for(date(2026, 3, 27), date(2026, 3, 30), "Europe/London")  # Fri .. Mon
    rules = [WeeklyRule("unavailable", d, 9 * 60, 17 * 60) for d in (4, 0)]
    assert expand_calendar(rules, [], horizon).unavailable == [
        (utc(2026, 3, 27, 9), utc(2026, 3, 27, 17)),  # GMT
        (utc(2026, 3, 30, 8), utc(2026, 3, 30, 16)),  # BST
    ]


def test_DOM_02_london_fall_back_day() -> None:
    horizon = horizon_for(date(2026, 10, 24), date(2026, 10, 26), "Europe/London")  # Sat .. Mon
    sunday_morning = WeeklyRule("preferred", 6, 0, 6 * 60)
    # 00:00 BST = 23:00Z Sat; 06:00 GMT = 06:00Z: the window is 7 hours long.
    assert expand_calendar([sunday_morning], [], horizon).preferred == [
        (utc(2026, 10, 24, 23), utc(2026, 10, 25, 6))
    ]


def test_DOM_02_rule_inside_a_dst_gap_yields_nothing() -> None:
    horizon = horizon_for(date(2026, 3, 8), date(2026, 3, 8), "America/New_York")
    gap = WeeklyRule("unavailable", 6, 2 * 60, 3 * 60)  # 02:00-03:00 does not exist that day
    assert expand_calendar([gap], [], horizon).unavailable == []


def test_DOM_02_windows_are_merged_and_clipped() -> None:
    early = DatedException("avoided", utc(2027, 1, 1), utc(2027, 1, 11, 6))
    late = DatedException("avoided", utc(2027, 1, 11, 5), utc(2027, 1, 11, 7))
    assert expand_calendar([], [early, late], KAMPALA).avoided == [
        (KAMPALA.start, utc(2027, 1, 11, 7))
    ]
