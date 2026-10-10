from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.regeneration import regenerate_for_slot_template, regenerate_schedule
from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import Conflict, NotFound, Unprocessable, field_error
from cartlyf_api.schedules import repository as repo
from cartlyf_api.schedules.models import Schedule, SlotTemplate
from cartlyf_api.schedules.schemas import (
    DayParts,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    SlotTemplateDefinition,
    SlotTemplateResponse,
    SlotTemplateWrite,
    horizon_errors,
)


def schedule_response(row: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=row.id,
        name=row.name,
        timezone=row.timezone,
        start_date=row.start_date,
        end_date=row.end_date,
        day_parts=DayParts.model_validate(row.day_parts),
    )


def slot_template_response(row: SlotTemplate) -> SlotTemplateResponse:
    return SlotTemplateResponse(
        id=row.id,
        schedule_id=row.schedule_id,
        name=row.name,
        definition=SlotTemplateDefinition.model_validate(row.definition),
    )


async def live_schedule(session: AsyncSession, principal: Principal, schedule_id: UUID) -> Schedule:
    schedule = await repo.get_schedule(session, principal.organisation_id, schedule_id)
    if schedule is None:
        raise NotFound("Unknown schedule")
    return schedule


async def _slot_template(
    session: AsyncSession, principal: Principal, schedule_id: UUID, slot_template_id: UUID
) -> SlotTemplate:
    template = await repo.get_slot_template(
        session, principal.organisation_id, schedule_id, slot_template_id
    )
    if template is None:
        raise NotFound("Unknown slot template")
    return template


async def create_schedule(
    session: AsyncSession, principal: Principal, body: ScheduleCreate
) -> ScheduleResponse:
    principal.require(Permission.CONFIG_MANAGE)
    schedule_id = uuid4()
    await repo.insert_schedule(
        session,
        {
            "id": schedule_id,
            "organisation_id": principal.organisation_id,
            "name": body.name,
            "timezone": body.timezone,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "day_parts": body.day_parts.model_dump(mode="json"),
        },
    )
    await record_change(session, principal, "schedule.created", "schedule", schedule_id)
    return ScheduleResponse(id=schedule_id, **body.model_dump())


async def list_schedules(session: AsyncSession, principal: Principal) -> list[ScheduleResponse]:
    principal.require(Permission.CONFIG_READ)
    rows = await repo.list_schedules(session, principal.organisation_id)
    return [schedule_response(row) for row in rows]


async def get_schedule(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> ScheduleResponse:
    principal.require(Permission.CONFIG_READ)
    return schedule_response(await live_schedule(session, principal, schedule_id))


async def update_schedule(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: ScheduleUpdate
) -> ScheduleResponse:
    principal.require(Permission.CONFIG_MANAGE)
    current = schedule_response(await live_schedule(session, principal, schedule_id))
    changes = body.model_dump(exclude_unset=True)
    if nulls := sorted(name for name, value in changes.items() if value is None):
        raise Unprocessable([field_error(("body", name), "may not be null") for name in nulls])
    merged = current.model_copy(
        update={**changes, "day_parts": body.day_parts or current.day_parts}
    )
    if errors := horizon_errors(merged.start_date, merged.end_date):
        raise Unprocessable([field_error(("body", name), msg) for name, msg in errors])
    if changes:
        values: dict[str, object] = {name: getattr(merged, name) for name in changes}
        if "day_parts" in values:
            values["day_parts"] = merged.day_parts.model_dump(mode="json")
        await repo.update_schedule(session, principal.organisation_id, schedule_id, values)
        pins_removed = 0
        if changes.keys() & {"timezone", "start_date", "end_date"}:
            schedule = await live_schedule(session, principal, schedule_id)
            pins_removed = await regenerate_schedule(session, principal, schedule)
        await record_change(
            session,
            principal,
            "schedule.updated",
            "schedule",
            schedule_id,
            {"fields": sorted(changes), "pins_removed": pins_removed},
        )
    return merged


async def delete_schedule(session: AsyncSession, principal: Principal, schedule_id: UUID) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    await repo.update_schedule(
        session, principal.organisation_id, schedule_id, {"deleted_at": func.now()}
    )
    await record_change(session, principal, "schedule.deleted", "schedule", schedule_id)


async def create_slot_template(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: SlotTemplateWrite
) -> SlotTemplateResponse:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    template_id = uuid4()
    await repo.insert_slot_template(
        session,
        {
            "id": template_id,
            "organisation_id": principal.organisation_id,
            "schedule_id": schedule_id,
            "name": body.name,
            "definition": body.definition.model_dump(mode="json"),
        },
    )
    await record_change(session, principal, "slot_template.created", "slot_template", template_id)
    return SlotTemplateResponse(id=template_id, schedule_id=schedule_id, **body.model_dump())


async def list_slot_templates(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[SlotTemplateResponse]:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    rows = await repo.slot_templates_for(session, principal.organisation_id, schedule_id)
    return [slot_template_response(row) for row in rows]


async def get_slot_template(
    session: AsyncSession, principal: Principal, schedule_id: UUID, slot_template_id: UUID
) -> SlotTemplateResponse:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    return slot_template_response(
        await _slot_template(session, principal, schedule_id, slot_template_id)
    )


async def replace_slot_template(
    session: AsyncSession,
    principal: Principal,
    schedule_id: UUID,
    slot_template_id: UUID,
    body: SlotTemplateWrite,
) -> SlotTemplateResponse:
    principal.require(Permission.CONFIG_MANAGE)
    schedule = await live_schedule(session, principal, schedule_id)
    await _slot_template(session, principal, schedule_id, slot_template_id)
    await repo.replace_slot_template(
        session,
        principal.organisation_id,
        slot_template_id,
        {"name": body.name, "definition": body.definition.model_dump(mode="json")},
    )
    template = await _slot_template(session, principal, schedule_id, slot_template_id)
    pins_removed = await regenerate_for_slot_template(session, principal, schedule, template)
    await record_change(
        session,
        principal,
        "slot_template.updated",
        "slot_template",
        slot_template_id,
        {"pins_removed": pins_removed},
    )
    return SlotTemplateResponse(id=slot_template_id, schedule_id=schedule_id, **body.model_dump())


async def delete_slot_template(
    session: AsyncSession, principal: Principal, schedule_id: UUID, slot_template_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    await _slot_template(session, principal, schedule_id, slot_template_id)
    if await repo.slot_template_in_use(session, org, slot_template_id):
        raise Conflict("The slot template is used by demands")
    await repo.delete_slot_template(session, org, slot_template_id)
    await record_change(
        session, principal, "slot_template.deleted", "slot_template", slot_template_id
    )
