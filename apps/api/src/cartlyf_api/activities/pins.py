from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as repo
from cartlyf_api.activities.models import Activity, Pin
from cartlyf_api.activities.schemas import PinResponse, PinWrite, RequirementSpec
from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import FieldError, NotFound, Unprocessable, field_error
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.schedules.service import live_schedule


def pin_response(pin: Pin) -> PinResponse:
    return PinResponse(
        activity_id=pin.activity_id,
        start_at=pin.start_at.astimezone(UTC) if pin.start_at else None,
        resources={role: [UUID(i) for i in ids] for role, ids in pin.resources.items()},
    )


def pin_errors(
    body: PinWrite, activity: Activity, requirements: Sequence[RequirementSpec]
) -> list[FieldError]:
    if body.start_at is None and not body.resources:
        return [field_error(("body",), "set start_at or resources")]
    errors: list[FieldError] = []
    starts = {s.astimezone(UTC) for s in activity.candidate_starts}
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


async def _activity(
    session: AsyncSession, principal: Principal, schedule_id: UUID, activity_id: UUID
) -> Activity:
    activity = await repo.get_activity(session, principal.organisation_id, schedule_id, activity_id)
    if activity is None:
        raise NotFound("Unknown activity")
    return activity


async def put_pin(
    session: AsyncSession,
    principal: Principal,
    schedule_id: UUID,
    activity_id: UUID,
    body: PinWrite,
) -> PinResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    activity = await _activity(session, principal, schedule_id, activity_id)
    resource_ids = {i for ids in body.resources.values() for i in ids}
    if await resources_repo.missing_resource_ids(session, org, resource_ids):
        raise NotFound("Unknown resource")
    rows = (await repo.requirements_for(session, org, [activity_id])).get(activity_id, [])
    if errors := pin_errors(body, activity, [repo.requirement_spec(r) for r in rows]):
        raise Unprocessable(errors)
    resources = {role: sorted({str(i) for i in ids}) for role, ids in body.resources.items()}
    start_at = body.start_at.astimezone(UTC) if body.start_at else None
    await repo.upsert_pin(session, org, schedule_id, activity_id, start_at, resources)
    await record_change(session, principal, "pin.set", "activity", activity_id)
    return PinResponse(
        activity_id=activity_id,
        start_at=start_at,
        resources={role: [UUID(i) for i in ids] for role, ids in resources.items()},
    )


async def list_pins(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[PinResponse]:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    pins = await repo.pins_for(session, principal.organisation_id, schedule_id)
    return [pin_response(pin) for pin in pins.values()]


async def delete_pin(
    session: AsyncSession, principal: Principal, schedule_id: UUID, activity_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    await _activity(session, principal, schedule_id, activity_id)
    if not await repo.delete_pin(session, principal.organisation_id, activity_id):
        raise NotFound("The activity is not pinned")
    await record_change(session, principal, "pin.deleted", "activity", activity_id)
