from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as repo
from cartlyf_api.activities.expansion import ExpansionError, expand_demand
from cartlyf_api.activities.models import Demand
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
    """Replace the demand's activities with a fresh expansion. Raises ExpansionError."""
    slots = SlotTemplateDefinition.model_validate(template.definition).slots
    drafts = expand_demand(demand.name, stored_spec(demand), slots, schedule.horizon())
    pins_removed = await repo.delete_demand_activities(session, org, demand.id)
    await repo.insert_activities(session, org, schedule.id, demand.id, drafts)
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
