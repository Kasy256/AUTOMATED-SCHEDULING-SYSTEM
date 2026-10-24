from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as repo
from cartlyf_api.activities.expansion import ExpansionError
from cartlyf_api.activities.models import Demand
from cartlyf_api.activities.references import check_requirement_refs
from cartlyf_api.activities.regeneration import Regenerated, regenerate_demand, stored_spec
from cartlyf_api.activities.schemas import DemandResponse, DemandWrite
from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.constraints.references import rules_referencing
from cartlyf_api.errors import Conflict, NotFound, Unprocessable, field_error
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.schedules.models import Schedule, SlotTemplate
from cartlyf_api.schedules.service import live_schedule


def _response(demand: Demand, activity_count: int) -> DemandResponse:
    return DemandResponse(
        id=demand.id,
        schedule_id=demand.schedule_id,
        name=demand.name,
        slot_template_id=demand.slot_template_id,
        spec=stored_spec(demand),
        activity_count=activity_count,
    )


async def _slot_template(
    session: AsyncSession, principal: Principal, schedule_id: UUID, slot_template_id: UUID
) -> SlotTemplate:
    template = await schedules_repo.get_slot_template(
        session, principal.organisation_id, schedule_id, slot_template_id
    )
    if template is None:
        raise NotFound("Unknown slot template")
    return template


async def persist_demand(
    session: AsyncSession,
    org: UUID,
    schedule: Schedule,
    template: SlotTemplate,
    demand_id: UUID,
    body: DemandWrite,
    *,
    created: bool,
) -> Regenerated:
    """Insert or update the demand row and regenerate its activities. Raises ExpansionError."""
    values = {
        "name": body.name,
        "slot_template_id": body.slot_template_id,
        "kind": body.spec.kind,
        "spec": {"version": 1, **body.spec.model_dump(mode="json")},
    }
    if created:
        await repo.insert_demand(
            session,
            {"id": demand_id, "organisation_id": org, "schedule_id": schedule.id, **values},
        )
    else:
        await repo.update_demand(session, org, demand_id, values)
    demand = await repo.get_demand(session, org, schedule.id, demand_id)
    if demand is None:
        raise NotFound("Unknown demand")
    return await regenerate_demand(session, org, schedule, demand, template)


async def _write(
    session: AsyncSession,
    principal: Principal,
    schedule: Schedule,
    demand_id: UUID,
    body: DemandWrite,
    *,
    created: bool,
) -> DemandResponse:
    org = principal.organisation_id
    template = await _slot_template(session, principal, schedule.id, body.slot_template_id)
    await check_requirement_refs(session, org, body.spec.requirements)
    try:
        result = await persist_demand(
            session, org, schedule, template, demand_id, body, created=created
        )
    except ExpansionError as exc:
        raise Unprocessable([field_error(("body", *exc.loc), str(exc))]) from exc
    await record_change(
        session,
        principal,
        "demand.created" if created else "demand.updated",
        "demand",
        demand_id,
        {"activities": result.activities, "pins_removed": result.pins_removed},
    )
    return DemandResponse(
        id=demand_id,
        schedule_id=schedule.id,
        activity_count=result.activities,
        pins_removed=result.pins_removed,
        **body.model_dump(),
    )


async def create_demand(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: DemandWrite
) -> DemandResponse:
    principal.require(Permission.CONFIG_MANAGE)
    schedule = await live_schedule(session, principal, schedule_id)
    return await _write(session, principal, schedule, uuid4(), body, created=True)


async def replace_demand(
    session: AsyncSession,
    principal: Principal,
    schedule_id: UUID,
    demand_id: UUID,
    body: DemandWrite,
) -> DemandResponse:
    principal.require(Permission.CONFIG_MANAGE)
    schedule = await live_schedule(session, principal, schedule_id)
    if await repo.get_demand(session, principal.organisation_id, schedule_id, demand_id) is None:
        raise NotFound("Unknown demand")
    return await _write(session, principal, schedule, demand_id, body, created=False)


async def delete_demand(
    session: AsyncSession, principal: Principal, schedule_id: UUID, demand_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    if await repo.get_demand(session, org, schedule_id, demand_id) is None:
        raise NotFound("Unknown demand")
    if rules := await rules_referencing(session, org, series_id=demand_id):
        raise Conflict(f"The demand is named by rules: {', '.join(rules)}")
    pins_removed = await repo.delete_demand_activities(session, org, demand_id)
    await repo.update_demand(session, org, demand_id, {"deleted_at": func.now()})
    await record_change(
        session, principal, "demand.deleted", "demand", demand_id, {"pins_removed": pins_removed}
    )


async def list_demands(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[DemandResponse]:
    principal.require(Permission.CONFIG_READ)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    demands = await repo.live_demands(session, org, schedule_id)
    counts = await repo.activity_counts(session, org, [d.id for d in demands])
    return [_response(d, counts.get(d.id, 0)) for d in demands]


async def get_demand(
    session: AsyncSession, principal: Principal, schedule_id: UUID, demand_id: UUID
) -> DemandResponse:
    principal.require(Permission.CONFIG_READ)
    org = principal.organisation_id
    await live_schedule(session, principal, schedule_id)
    demand = await repo.get_demand(session, org, schedule_id, demand_id)
    if demand is None:
        raise NotFound("Unknown demand")
    counts = await repo.activity_counts(session, org, [demand_id])
    return _response(demand, counts.get(demand_id, 0))
