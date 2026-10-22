"""Writes the fairness ledger: what each person's published roster counted, by local day."""

from collections import Counter
from datetime import timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.fairness import repository
from cartlyf_api.fairness.repository import LedgerKey
from cartlyf_api.fairness.rules import fairness_rules
from cartlyf_api.versions.models import SolutionVersion
from cartlyf_api.versions.state import load_state
from cartlyf_engine.templates import fairness


async def record_published(session: AsyncSession, org: UUID, version: SolutionVersion) -> None:
    """Replace the schedule's ledger rows with what this version's fairness rules count."""
    state = await load_state(session, org, version)
    zone = ZoneInfo(state.run.timezone)
    origin = state.run.horizon_origin
    # Rules sharing a counter (one per staff group) may both cover a person: count a start once.
    starts: dict[tuple[str, str], set[int]] = {}
    for instance, params in fairness_rules(state.problem.constraints):
        counted = fairness.counted(state.problem, instance, state.assignments.values())
        for resource_id, minutes in counted.items():
            starts.setdefault((resource_id, params.counter), set()).update(minutes)
    counts: Counter[LedgerKey] = Counter()
    for (resource_id, counter), minutes in starts.items():
        for start in minutes:
            day = (origin + timedelta(minutes=start)).astimezone(zone).date()
            counts[UUID(resource_id), counter, day] += 1
    await repository.delete_schedule_rows(session, org, version.schedule_id)
    await repository.insert_rows(session, org, version.schedule_id, version.id, counts)


async def clear_schedule(session: AsyncSession, org: UUID, schedule_id: UUID) -> None:
    await repository.delete_schedule_rows(session, org, schedule_id)
