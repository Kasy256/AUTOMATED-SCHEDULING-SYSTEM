from datetime import UTC, date, datetime, timedelta

import pytest

from cartlyf_api.activities.expansion import ExpansionError, expand_demand
from cartlyf_api.activities.schemas import DEMAND_SPEC, CoverageDemandSpec, SessionDemandSpec
from cartlyf_api.schedules.schemas import Slot
from cartlyf_api.schedules.time_grid import horizon_for

WEEKDAYS = [0, 1, 2, 3, 4]
PERIODS = [
    Slot(label="P1", weekdays=WEEKDAYS, start_minute=510, duration_minutes=115),
    Slot(label="P2", weekdays=WEEKDAYS, start_minute=660, duration_minutes=115),
    Slot(label="P3", weekdays=WEEKDAYS, start_minute=840, duration_minutes=115),
    Slot(label="P4", weekdays=WEEKDAYS, start_minute=990, duration_minutes=115),
]
SHIFTS = [
    Slot(label="day", weekdays=[0, 1, 2, 3, 4, 5, 6], start_minute=420, duration_minutes=480),
    Slot(label="evening", weekdays=[0, 1, 2, 3, 4, 5, 6], start_minute=900, duration_minutes=480),
    Slot(label="night", weekdays=[0, 1, 2, 3, 4, 5, 6], start_minute=1380, duration_minutes=480),
]
REQS = [{"role": "lecturer", "count_min": 1, "count_max": 1}]
ONE_WEEK = horizon_for(date(2027, 1, 11), date(2027, 1, 15), "Africa/Kampala")


def session(**spec: object) -> SessionDemandSpec | CoverageDemandSpec:
    return DEMAND_SPEC.validate_python({"kind": "session", "requirements": REQS} | spec)


def coverage(**spec: object) -> SessionDemandSpec | CoverageDemandSpec:
    reqs = [
        {"role": "nurse", "count_min": 3, "count_max": 3, "tags": ["RN"]},
        {"role": "midwife", "count_min": 1, "count_max": 1, "hard": False, "weight": 50},
    ]
    return DEMAND_SPEC.validate_python({"kind": "coverage", "requirements": reqs} | spec)


def test_DOM_03_one_week_gives_sessions_per_week_activities() -> None:
    drafts = expand_demand("Calculus", session(sessions_per_week=2), PERIODS, ONE_WEEK)
    assert len(drafts) == 2
    for draft in drafts:
        assert draft.duration_minutes == 115
        assert len(draft.candidate_starts) == 20  # 4 periods x 5 days
        assert draft.candidate_starts[0] == datetime(2027, 1, 11, 5, 30, tzinfo=UTC)
        assert list(draft.candidate_starts) == sorted(draft.candidate_starts)
        assert [r.role for r in draft.requirements] == ["lecturer"]


def test_DOM_03_multi_week_horizon_repeats_per_week() -> None:
    three_weeks = horizon_for(date(2027, 1, 11), date(2027, 1, 29), "Africa/Kampala")
    drafts = expand_demand("Calculus", session(sessions_per_week=2), PERIODS, three_weeks)
    assert len(drafts) == 6
    first, last = drafts[0], drafts[-1]
    assert max(first.candidate_starts) < min(last.candidate_starts)
    assert all(len(d.candidate_starts) == 20 for d in drafts)


def test_DOM_03_partial_week_and_weeks_without_slots() -> None:
    weekend_start = horizon_for(date(2027, 1, 16), date(2027, 1, 19), "Africa/Kampala")  # Sat..Tue
    drafts = expand_demand("Calculus", session(sessions_per_week=1), PERIODS, weekend_start)
    assert len(drafts) == 1  # the Sat-Sun week has no teaching slots, so it gets none
    assert len(drafts[0].candidate_starts) == 8  # Mon + Tue x 4 periods


def test_DOM_03_slot_label_filter_and_explicit_duration() -> None:
    drafts = expand_demand(
        "Lab",
        session(sessions_per_week=1, slot_labels=["P3"], duration_minutes=90),
        PERIODS,
        ONE_WEEK,
    )
    assert drafts[0].duration_minutes == 90 and len(drafts[0].candidate_starts) == 5


def test_DOM_03_mixed_slot_durations_need_an_explicit_duration() -> None:
    mixed = [*PERIODS[:1], Slot(label="Long", weekdays=[0], start_minute=900, duration_minutes=180)]
    with pytest.raises(ExpansionError, match="duration_minutes") as caught:
        expand_demand("X", session(sessions_per_week=1), mixed, ONE_WEEK)
    assert caught.value.loc == ("spec", "duration_minutes")


def test_DOM_03_unknown_slot_label() -> None:
    with pytest.raises(ExpansionError, match="P9") as caught:
        expand_demand("X", session(sessions_per_week=1, slot_labels=["P9"]), PERIODS, ONE_WEEK)
    assert caught.value.loc == ("spec", "slot_labels")


def test_DOM_03_slot_starts_keep_wall_clock_across_dst() -> None:
    london = horizon_for(date(2026, 3, 23), date(2026, 4, 3), "Europe/London")
    drafts = expand_demand("X", session(sessions_per_week=1, slot_labels=["P1"]), PERIODS, london)
    assert drafts[0].candidate_starts[0] == datetime(2026, 3, 23, 8, 30, tzinfo=UTC)  # GMT
    assert drafts[1].candidate_starts[0] == datetime(2026, 3, 30, 7, 30, tzinfo=UTC)  # BST


def test_DOM_04_coverage_is_one_activity_per_date_and_shift() -> None:
    week = horizon_for(date(2027, 1, 11), date(2027, 1, 17), "Africa/Kampala")
    drafts = expand_demand("Ward A", coverage(), SHIFTS, week)
    assert len(drafts) == 21
    assert all(len(d.candidate_starts) == 1 for d in drafts)
    assert [r.count_min for r in drafts[0].requirements] == [3, 1]
    assert drafts[0].requirements[1].hard is False
    night = next(d for d in drafts if d.name == "Ward A 2027-01-17 night")
    assert night.candidate_starts[0] == datetime(2027, 1, 17, 20, tzinfo=UTC)
    assert night.candidate_starts[0] + timedelta(minutes=night.duration_minutes) > week.end


def test_DOM_04_coverage_slot_filter() -> None:
    week = horizon_for(date(2027, 1, 11), date(2027, 1, 17), "Africa/Kampala")
    drafts = expand_demand("Ward A", coverage(slot_labels=["night"]), SHIFTS, week)
    assert len(drafts) == 7


@pytest.mark.parametrize(
    "requirements",
    [
        [],
        [{"role": "a", "count_min": 2, "count_max": 1}],
        [{"role": "a"}, {"role": "a"}],
        [{"role": "a", "hard": False}],
    ],
)
def test_requirement_specs_are_validated(requirements: list[object]) -> None:
    with pytest.raises(ValueError):
        DEMAND_SPEC.validate_python(
            {"kind": "session", "sessions_per_week": 1, "requirements": requirements}
        )


def test_generated_names_fit_the_200_character_limit() -> None:
    long_name = "N" * 200
    week = horizon_for(date(2027, 1, 11), date(2027, 1, 17), "Africa/Kampala")
    long_label = [Slot(label="L" * 50, weekdays=[0], start_minute=420, duration_minutes=60)]
    drafts = expand_demand(long_name, coverage(), long_label, week)
    drafts += expand_demand(long_name, session(sessions_per_week=12), PERIODS, ONE_WEEK)
    assert all(len(d.name) <= 200 for d in drafts)
    assert drafts[0].name.endswith("2027-01-11 " + "L" * 50)


def test_session_keys_name_the_week_monday_and_position() -> None:
    three_weeks = horizon_for(date(2027, 1, 11), date(2027, 1, 29), "Africa/Kampala")
    drafts = expand_demand("Calculus", session(sessions_per_week=2), PERIODS, three_weeks)
    assert [d.key for d in drafts] == [
        "2027-01-11#1",
        "2027-01-11#2",
        "2027-01-18#1",
        "2027-01-18#2",
        "2027-01-25#1",
        "2027-01-25#2",
    ]
    midweek = horizon_for(date(2027, 1, 13), date(2027, 1, 22), "Africa/Kampala")
    later = expand_demand("Calculus", session(sessions_per_week=1), PERIODS, midweek)
    assert [d.key for d in later] == ["2027-01-11#1", "2027-01-18#1"]


def test_coverage_keys_name_the_date_and_slot() -> None:
    drafts = expand_demand("Ward", coverage(), SHIFTS, ONE_WEEK)
    assert drafts[0].key == "2027-01-11|day"
    assert len({d.key for d in drafts}) == len(drafts)


def test_coverage_activities_get_slot_and_weekday() -> None:
    day = [SHIFTS[0]]
    week = horizon_for(date(2027, 1, 11), date(2027, 1, 17), "Africa/Kampala")
    drafts = expand_demand("Ward", coverage(attrs={"ward": "A"}), day, week)
    assert len(drafts) == 7
    assert [d.attrs["weekday"] for d in drafts] == [1, 2, 3, 4, 5, 6, 7]
    assert all(d.attrs["slot"] == "day" and d.attrs["ward"] == "A" for d in drafts)


def test_coverage_night_shift_takes_its_start_weekday() -> None:
    week = horizon_for(date(2027, 1, 11), date(2027, 1, 17), "Africa/Kampala")
    drafts = expand_demand("Ward", coverage(slot_labels=["night"]), SHIFTS, week)
    friday = next(d for d in drafts if d.key == "2027-01-15|night")
    assert friday.attrs["weekday"] == 5


def test_session_activities_get_no_generated_attrs() -> None:
    drafts = expand_demand("Calculus", session(sessions_per_week=2), PERIODS, ONE_WEEK)
    assert all("slot" not in d.attrs and "weekday" not in d.attrs for d in drafts)
