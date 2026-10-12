from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as repo
from cartlyf_api.activities.expansion import ActivityDraft, ExpansionError, expand_demand
from cartlyf_api.activities.models import Demand
from cartlyf_api.activities.pin_rules import pin_errors, pin_write
from cartlyf_api.activities.schemas import DEMAND_SPEC, CoverageDemandSpec, SessionDemandSpec
from cartlyf_api.auth.permissions import Principal
from cartlyf_api.errors import Conflict
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.schedules.models import Schedule, SlotTemplate
from cartlyf_api.schedules.schemas import SlotTemplateDefinition


@dataclass(frozen=True)
class Regenerated:
    activities: int
    pins_removed: int


def stored_spec(demand: Demand) -> SessionDemandSpec | CoverageDemandSpec:
    return DEMAND_SPEC.validate_python({k: v for k, v in demand.spec.items() if k != "version"})


async def regenerate_demand(
    session: AsyncSession, org: UUID, schedule: Schedule, demand: Demand, template: SlotTemplate
) -> Regenerated:
    """Bring the demand's activities in line with a fresh expansion. Activities whose natural key
    survives keep their id and, if it still fits, their pin. Raises ExpansionError."""
    slots = SlotTemplateDefinition.model_validate(template.definition).slots
    drafts = expand_demand(demand.name, stored_spec(demand), slots, schedule.horizon())
    current = await repo.demand_activities(session, org, demand.id)
    by_key = {a.natural_key: a for a in current if a.natural_key is not None}
    pins = await repo.pins_for(session, org, schedule.id)
    kept: set[UUID] = set()
    fresh: list[ActivityDraft] = []
    pins_removed = 0
    for draft in drafts:
        activity = by_key.get(draft.key) if draft.key is not None else None
        if activity is None:
            fresh.append(draft)
            continue
        kept.add(activity.id)
        await repo.update_activity(
            session,
            org,
            activity.id,
            name=draft.name,
            duration_minutes=draft.duration_minutes,
            candidate_starts=draft.candidate_starts,
            attrs=draft.attrs,
        )
        await repo.replace_requirements(session, org, activity.id, draft.requirements)
        pin = pins.get(activity.id)
        if pin is not None and pin_errors(
            pin_write(pin), draft.candidate_starts, draft.requirements
        ):
            await repo.delete_pin(session, org, activity.id)
            pins_removed += 1
    gone = [a.id for a in current if a.id not in kept]
    pins_removed += sum(1 for activity_id in gone if activity_id in pins)
    await repo.delete_activities(session, org, gone)
    await repo.insert_activities(session, org, schedule.id, demand.id, fresh)
    return Regenerated(len(drafts), pins_removed)


async def _regenerate_all(
    session: AsyncSession, principal: Principal, schedule: Schedule, demands: list[Demand]
) -> int:
    org, removed = principal.organisation_id, 0
    for demand in demands:
        template = await schedules_repo.get_slot_template(
            session, org, schedule.id, demand.slot_template_id
        )
        if template is None:
            raise Conflict(f"Demand '{demand.name}' has no slot template")
        try:
            result = await regenerate_demand(session, org, schedule, demand, template)
        except ExpansionError as exc:
            raise Conflict(f"Demand '{demand.name}' no longer fits: {exc}") from exc
        removed += result.pins_removed
    return removed


async def regenerate_schedule(
    session: AsyncSession, principal: Principal, schedule: Schedule
) -> int:
    """After the schedule's dates or timezone change; returns pins removed."""
    org = principal.organisation_id
    horizon = schedule.horizon()
    outside = [
        a.name
        for a in await repo.manual_activities(session, org, schedule.id)
        if any(not horizon.start <= s < horizon.end for s in a.candidate_starts)
    ]
    if outside:
        raise Conflict(
            f"{len(outside)} manual activities fall outside the new dates, e.g. {outside[0]}"
        )
    demands = list(await repo.live_demands(session, org, schedule.id))
    return await _regenerate_all(session, principal, schedule, demands)


async def regenerate_for_slot_template(
    session: AsyncSession, principal: Principal, schedule: Schedule, template: SlotTemplate
) -> int:
    demands = list(await repo.demands_using(session, principal.organisation_id, template.id))
    return await _regenerate_all(session, principal, schedule, demands)
