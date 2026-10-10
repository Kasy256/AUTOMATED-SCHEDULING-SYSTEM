from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.constraints import repository as repo
from cartlyf_api.constraints.models import ConstraintInstanceRow
from cartlyf_api.errors import NotFound
from cartlyf_engine.templates.registry import params_references


@dataclass(frozen=True)
class RuleReferences:
    series_ids: frozenset[UUID]
    resource_ids: frozenset[UUID]
    resource_type_ids: frozenset[UUID]


def as_uuids(values: Iterable[str]) -> frozenset[UUID]:
    """Ids from params are free text until resolved; one that is not a UUID names nothing."""
    try:
        return frozenset(UUID(v) for v in values)
    except ValueError as exc:
        raise NotFound("Unknown id in rule parameters") from exc


def references_of(row: ConstraintInstanceRow) -> RuleReferences:
    named = params_references(row.template_key, row.template_version, row.params)
    scope = row.scope
    return RuleReferences(
        series_ids=as_uuids(named.series_ids) | as_uuids(scope["series_ids"]),
        resource_ids=as_uuids(named.resource_ids) | as_uuids(scope["resource_ids"]),
        resource_type_ids=as_uuids(scope["resource_type_ids"]),
    )


async def rules_referencing(
    session: AsyncSession,
    org: UUID,
    *,
    resource_id: UUID | None = None,
    series_id: UUID | None = None,
    resource_type_id: UUID | None = None,
) -> list[str]:
    """Names of live rules that name this resource, demand (series) or resource type."""
    names: list[str] = []
    for row in await repo.live_constraints(session, org):
        refs = references_of(row)
        if (
            resource_id in refs.resource_ids
            or series_id in refs.series_ids
            or resource_type_id in refs.resource_type_ids
        ):
            names.append(row.name)
    return names
