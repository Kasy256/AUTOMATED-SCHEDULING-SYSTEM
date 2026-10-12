"""Whether a pin fits an activity; shared by the pin endpoint and demand regeneration."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from cartlyf_api.activities.models import Pin
from cartlyf_api.activities.schemas import PinWrite, RequirementSpec
from cartlyf_api.errors import FieldError, field_error


def pin_write(pin: Pin) -> PinWrite:
    return PinWrite(
        start_at=pin.start_at,
        resources={role: [UUID(i) for i in ids] for role, ids in pin.resources.items()},
    )


def pin_errors(
    body: PinWrite, candidate_starts: Sequence[datetime], requirements: Sequence[RequirementSpec]
) -> list[FieldError]:
    if body.start_at is None and not body.resources:
        return [field_error(("body",), "set start_at or resources")]
    errors: list[FieldError] = []
    starts = {s.astimezone(UTC) for s in candidate_starts}
    if body.start_at is not None and body.start_at.astimezone(UTC) not in starts:
        errors.append(
            field_error(("body", "start_at"), "must be one of the activity's candidate starts")
        )
    by_role = {r.role: r for r in requirements}
    for role, resource_ids in body.resources.items():
        requirement = by_role.get(role)
        if requirement is None:
            errors.append(field_error(("body", "resources", role), "the activity has no such role"))
        elif len(set(resource_ids)) > requirement.count_max:
            errors.append(
                field_error(("body", "resources", role), "more resources than the role allows")
            )
    return errors
