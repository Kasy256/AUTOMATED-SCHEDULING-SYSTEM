from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from cartlyf_api.types import MAX_HORIZON_DAYS, Name, TimeZoneName
from cartlyf_engine.domain import Key

DayMinute = Annotated[int, Field(ge=0, le=1439)]
EndMinute = Annotated[int, Field(ge=1, le=1440)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


def _distinct_weekdays(days: list[int]) -> list[int]:
    if len(set(days)) != len(days):
        raise ValueError("weekdays must be distinct")
    return sorted(days)


Weekdays = Annotated[
    list[Annotated[int, Field(ge=0, le=6)]], Field(min_length=1), AfterValidator(_distinct_weekdays)
]


class DayPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Key
    start_minute: DayMinute
    end_minute: EndMinute

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_minute <= self.start_minute:
            raise ValueError("end_minute must be after start_minute")
        return self


class DayParts(BaseModel):
    """Named parts of each day (e.g. morning/afternoon) that rules can refer to."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    parts: list[DayPart] = Field(default_factory=list[DayPart], max_length=24)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        names = [p.name for p in self.parts]
        if len(set(names)) != len(names):
            raise ValueError("day part names must be unique")
        return self


def horizon_errors(start_date: date, end_date: date) -> list[tuple[str, str]]:
    """(field, message) pairs; shared by create and the merged result of a PATCH."""
    if end_date < start_date:
        return [("end_date", "end_date must not be before start_date")]
    if (end_date - start_date).days >= MAX_HORIZON_DAYS:
        return [("end_date", f"a schedule spans at most {MAX_HORIZON_DAYS} days")]
    return []


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Term 1 2027",
                    "timezone": "Africa/Kampala",
                    "start_date": "2027-01-11",
                    "end_date": "2027-01-15",
                    "day_parts": {
                        "version": 1,
                        "parts": [
                            {"name": "morning", "start_minute": 480, "end_minute": 780},
                            {"name": "afternoon", "start_minute": 780, "end_minute": 1080},
                        ],
                    },
                }
            ]
        },
    )

    name: Name
    timezone: TimeZoneName
    start_date: date
    end_date: date
    day_parts: DayParts = Field(default_factory=DayParts)

    @model_validator(mode="after")
    def _horizon(self) -> Self:
        if errors := horizon_errors(self.start_date, self.end_date):
            raise ValueError(errors[0][1])
        return self


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"name": "Term 1"}]})

    name: Name | None = None
    timezone: TimeZoneName | None = None
    start_date: date | None = None
    end_date: date | None = None
    day_parts: DayParts | None = None


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    timezone: str
    start_date: date
    end_date: date
    day_parts: DayParts


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Label
    weekdays: Weekdays
    start_minute: DayMinute
    # May run past midnight (night shifts); elapsed minutes, not wall-clock.
    duration_minutes: Annotated[int, Field(ge=1, le=1440)]


class SlotTemplateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    slots: list[Slot] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _unique_labels(self) -> Self:
        labels = [s.label for s in self.slots]
        if len(set(labels)) != len(labels):
            raise ValueError("slot labels must be unique")
        return self


class SlotTemplateWrite(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Teaching periods",
                    "definition": {
                        "version": 1,
                        "slots": [
                            {
                                "label": "P1",
                                "weekdays": [0, 1, 2, 3, 4],
                                "start_minute": 510,
                                "duration_minutes": 115,
                            },
                            {
                                "label": "P2",
                                "weekdays": [0, 1, 2, 3, 4],
                                "start_minute": 660,
                                "duration_minutes": 115,
                            },
                        ],
                    },
                }
            ]
        },
    )

    name: Name
    definition: SlotTemplateDefinition


class SlotTemplateResponse(SlotTemplateWrite):
    id: UUID
    schedule_id: UUID
