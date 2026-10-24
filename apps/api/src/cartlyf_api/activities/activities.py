from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as repo
from cartlyf_api.activities.expansion import ActivityDraft
from cartlyf_api.activities.models import Activity
from cartlyf_api.activities.references import check_requirement_refs
from cartlyf_api.activities.schemas import ActivityResponse, ActivityWrite
from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import Conflict, FieldError, NotFound, Unprocessable, field_error
from cartlyf_api.schedules.service import live_schedule
from cartlyf_api.schedules.time_grid import Horizon


def start_errors(starts: Sequence[datetime], horizon: Horizon) -> list[FieldError]:
    errors: list[FieldError] = []
    for i, start in enumerate(starts):
        if start.second or start.microsecond:
            errors.append(field_error(("body", "candidate_starts", i), "must be a whole minute"))
        elif not horizon.start <= start < horizon.end:
            errors.append(
                field_error(("body", "candidate_starts", i), "must be within the schedule's dates")
            )
    if len({s.astimezone(UTC) for s in starts}) != len(starts):
        errors.append(field_error(("body", "candidate_starts"), "must be distinct"))
    return errors


def draft_of(body: ActivityWrite) -> ActivityDraft:
    starts = tuple(sorted(s.astimezone(UTC) for s in body.candidate_starts))
    return ActivityDraft(
        None, body.name, body.duration_minutes, starts, tuple(body.requirements), body.attrs
    )


async def _activity(
    session: AsyncSession, principal: Principal, schedule_id: UUID, activity_id: UUID
) -> Activity:
    activity = await repo.get_activity(session, principal.organisation_id, schedule_id, activity_id)
    if activity is None:
        raise NotFound("Unknown activity")
    return activity


def _require_manual(activity: Activity) -> None:
    if activity.demand_id is not None:
        raise Conflict("This activity is generated from a demand; edit the demand instead")


async def _responses(
    session: AsyncSession, org: UUID, activities: Sequence[Activity]
) -> list[ActivityResponse]:
    requirements = await repo.requirements_for(session, org, [a.id for a in activities])
    return [
        ActivityResponse(
            id=a.id,
            schedule_id=a.schedule_id,
            demand_id=a.demand_id,
            series_id=a.series_id,
            name=a.name,
            duration_minutes=a.duration_minutes,
            candidate_starts=[s.astimezone(UTC) for s in a.candidate_starts],
            requirements=[repo.requirement_spec(r) for r in requirements.get(a.id, [])],
            attrs=a.attrs,
        )
        for a in activities
    ]


async def list_activities(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[ActivityResponse]:
    principal.require(Permission.CONFIG_READ)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    return await _responses(session, org, await repo.list_activities(session, org, schedule_id))


async def get_activity(
    session: AsyncSession, principal: Principal, schedule_id: UUID, activity_id: UUID
) -> ActivityResponse:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    activity = await _activity(session, principal, schedule_id, activity_id)
    [response] = await _responses(session, principal.organisation_id, [activity])
    return response


async def create_activity(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: ActivityWrite
) -> ActivityResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    schedule = await live_schedule(session, principal, schedule_id)
    await check_requirement_refs(session, org, body.requirements)
    if errors := start_errors(body.candidate_starts, schedule.horizon()):
        raise Unprocessable(errors)
    [activity_id] = await repo.insert_activities(session, org, schedule_id, None, [draft_of(body)])
    await record_change(session, principal, "activity.created", "activity", activity_id)
    return await get_activity(session, principal, schedule_id, activity_id)


async def replace_activity(
    session: AsyncSession,
    principal: Principal,
    schedule_id: UUID,
    activity_id: UUID,
    body: ActivityWrite,
) -> ActivityResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    schedule = await live_schedule(session, principal, schedule_id)
    _require_manual(await _activity(session, principal, schedule_id, activity_id))
    await check_requirement_refs(session, org, body.requirements)
    if errors := start_errors(body.candidate_starts, schedule.horizon()):
        raise Unprocessable(errors)
    draft = draft_of(body)
    pin = await repo.get_pin(session, org, activity_id)
    roles = {r.role for r in body.requirements}
    if pin is not None and (
        (pin.start_at is not None and pin.start_at.astimezone(UTC) not in draft.candidate_starts)
        or not set(pin.resources) <= roles
    ):
        raise Conflict("The activity is pinned; change or remove the pin first")
    await repo.update_activity(
        session,
        org,
        activity_id,
        name=draft.name,
        duration_minutes=draft.duration_minutes,
        candidate_starts=draft.candidate_starts,
        attrs=draft.attrs,
    )
    await repo.replace_requirements(session, org, activity_id, body.requirements)
    await record_change(session, principal, "activity.updated", "activity", activity_id)
    return await get_activity(session, principal, schedule_id, activity_id)


async def delete_activity(
    session: AsyncSession, principal: Principal, schedule_id: UUID, activity_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    _require_manual(await _activity(session, principal, schedule_id, activity_id))
    await repo.delete_activity(session, principal.organisation_id, activity_id)
    await record_change(session, principal, "activity.deleted", "activity", activity_id)
