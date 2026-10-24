"""Fairness history for a new problem, read from the ledger of earlier published rosters."""

from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.fairness import repository
from cartlyf_api.fairness.rules import fairness_rules
from cartlyf_api.schedules.models import Schedule
from cartlyf_engine.domain import ConstraintInstance


async def history_for(
    session: AsyncSession,
    org: UUID,
    schedule: Schedule,
    constraints: Sequence[ConstraintInstance],
    resource_ids: set[str],
) -> dict[str, dict[str, int]] | None:
    """Per fairness rule, each person's counts from other live schedules in the lookback before
    this schedule starts; None when no rule has any, so a ledger-free problem is unchanged."""
    ids = [UUID(r) for r in sorted(resource_ids)]
    totals: dict[tuple[str, int], dict[UUID, int]] = {}
    history: dict[str, dict[str, int]] = {}
    for instance, params in fairness_rules(constraints):
        key = (params.counter, params.lookback_days)
        if key not in totals:
            totals[key] = await repository.totals(
                session,
                org,
                exclude_schedule_id=schedule.id,
                counter=params.counter,
                since=schedule.start_date - timedelta(days=params.lookback_days),
                before=schedule.start_date,
                resource_ids=ids,
            )
        if counts := {str(r): n for r, n in totals[key].items() if n > 0}:
            history[instance.id] = dict(sorted(counts.items()))
    return history or None
