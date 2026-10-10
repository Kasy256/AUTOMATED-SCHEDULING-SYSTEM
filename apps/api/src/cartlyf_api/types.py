from functools import cache
from typing import Annotated
from zoneinfo import available_timezones

from pydantic import AfterValidator, StringConstraints

# Platform safety cap on one schedule's horizon, not a customer rule.
MAX_HORIZON_DAYS = 366

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


@cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def _known_timezone(value: str) -> str:
    if value not in _timezones():
        raise ValueError("unknown IANA timezone")
    return value


TimeZoneName = Annotated[str, AfterValidator(_known_timezone)]
