import re
from collections.abc import Collection, Iterator
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.permissions import Permission, Principal, Role
from cartlyf_api.errors import NotFound, Unprocessable, field_error
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.versions import repository
from cartlyf_api.versions.diff import Placed, diff
from cartlyf_api.versions.export import ExportRow, csv_rows
from cartlyf_api.versions.models import SolutionVersion
from cartlyf_api.versions.schemas import (
    AssignmentChange,
    AssignmentOut,
    MyAssignment,
    VersionDetail,
    VersionDiff,
    VersionStatus,
    VersionSummary,
)


def _summary(version: SolutionVersion) -> VersionSummary:
    return VersionSummary(
        id=version.id,
        schedule_id=version.schedule_id,
        number=version.number,
        status=_status(version.status),
        solver_status=version.solver_status,
        hard_violations=version.score["hard_violations"],
        soft_total=version.score["soft_total"],
        created_at=version.created_at,
        published_at=version.published_at,
        archived_at=version.archived_at,
        parent_version_id=version.parent_version_id,
        solve_run_id=version.solve_run_id,
    )


def _status(value: str) -> VersionStatus:
    if value == "draft" or value == "published" or value == "archived":
        return value
    raise ValueError(f"unexpected version status {value!r}")


async def _assignments(
    session: AsyncSession,
    org: UUID,
    version_id: UUID,
    resource_ids: Collection[UUID] | None = None,
) -> list[AssignmentOut]:
    rows = await repository.assignment_rows(session, org, version_id, resource_ids)
    resources = await repository.resources_by_activity(session, org, version_id)
    names = await repository.activity_names(session, org, [row.activity_id for row in rows])
    return [
        AssignmentOut(
            activity_id=row.activity_id,
            activity_name=names.get(row.activity_id),
            start_at=row.start_at,
            end_at=row.end_at,
            resources=resources.get(row.activity_id, {}),
        )
        for row in rows
    ]


def _placed(assignment: AssignmentOut) -> Placed:
    return assignment.start_at, {r: frozenset(ids) for r, ids in assignment.resources.items()}


async def require_version(
    session: AsyncSession, org: UUID, version_id: UUID, *, for_update: bool = False
) -> SolutionVersion:
    version = await repository.get_version(session, org, version_id, for_update=for_update)
    if version is None:
        raise NotFound("Unknown version")
    return version


async def version_detail(
    session: AsyncSession,
    org: UUID,
    version: SolutionVersion,
    resource_ids: Collection[UUID] | None = None,
) -> VersionDetail:
    assignments = await _assignments(session, org, version.id, resource_ids)
    return VersionDetail(
        **_summary(version).model_dump(), score=version.score, assignments=assignments
    )


async def list_versions(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[VersionSummary]:
    principal.require(Permission.VERSIONS_READ)
    org = principal.organisation_id
    if await schedules_repo.get_schedule(session, org, schedule_id) is None:
        raise NotFound("Unknown schedule")
    return [_summary(v) for v in await repository.list_versions(session, org, schedule_id)]


async def _readable_version(
    session: AsyncSession, principal: Principal, version_id: UUID
) -> tuple[SolutionVersion, list[UUID] | None]:
    """The version plus, for a member-only caller, the resources whose assignments they may see."""
    org = principal.organisation_id
    member_only = not principal.has(Permission.VERSIONS_READ)
    if member_only and Role.MEMBER not in principal.roles:
        principal.require(Permission.VERSIONS_READ)
    version = await require_version(session, org, version_id)
    if not member_only:
        return version, None
    if version.status != "published":
        raise NotFound("Unknown version")
    return version, await resources_repo.resource_ids_for_user(session, org, principal.user_id)


async def get_version(
    session: AsyncSession, principal: Principal, version_id: UUID
) -> VersionDetail:
    version, own = await _readable_version(session, principal, version_id)
    return await version_detail(session, principal.organisation_id, version, own)


async def export_csv(
    session: AsyncSession, principal: Principal, version_id: UUID
) -> tuple[str, Iterator[str]]:
    """(filename, CSV lines) for a version, with a member's export limited to their assignments."""
    org = principal.organisation_id
    version, own = await _readable_version(session, principal, version_id)
    schedule = await repository.schedule_of(session, org, version.schedule_id)
    assignments = await _assignments(session, org, version.id, own)
    ids = {rid for a in assignments for rids in a.resources.values() for rid in rids}
    names = await repository.resource_names(session, org, ids)
    rows = [
        ExportRow(
            activity_id=str(a.activity_id),
            activity=a.activity_name or str(a.activity_id),
            start_at=a.start_at,
            end_at=a.end_at,
            role=role,
            resource_code=names.get(rid, (str(rid), str(rid)))[0],
            resource=names.get(rid, (str(rid), str(rid)))[1],
        )
        for a in assignments
        for role, rids in a.resources.items()
        for rid in rids
    ]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", schedule.name).strip("_") or "schedule"
    return f"{stem}-v{version.number}.csv", csv_rows(rows, ZoneInfo(schedule.timezone))


async def diff_versions(
    session: AsyncSession, principal: Principal, version_id: UUID, other_version_id: UUID
) -> VersionDiff:
    principal.require(Permission.VERSIONS_READ)
    org = principal.organisation_id
    before = await require_version(session, org, version_id)
    after = await require_version(session, org, other_version_id)
    if before.schedule_id != after.schedule_id:
        raise Unprocessable(
            [field_error(("path", "other_version_id"), "must belong to the same schedule")]
        )
    old = {a.activity_id: a for a in await _assignments(session, org, version_id)}
    new = {a.activity_id: a for a in await _assignments(session, org, other_version_id)}
    result = diff({k: _placed(v) for k, v in old.items()}, {k: _placed(v) for k, v in new.items()})

    def changes(ids: list[UUID]) -> list[AssignmentChange]:
        return [AssignmentChange(activity_id=i, before=old.get(i), after=new.get(i)) for i in ids]

    return VersionDiff(
        added=changes(result.added),
        removed=changes(result.removed),
        moved=changes(result.moved),
        reassigned=changes(result.reassigned),
    )


async def my_assignments(session: AsyncSession, principal: Principal) -> list[MyAssignment]:
    org = principal.organisation_id
    own = await resources_repo.resource_ids_for_user(session, org, principal.user_id)
    if not own:
        return []
    mine = set(own)
    out: list[MyAssignment] = []
    for version, schedule_name in await repository.published_versions(session, org):
        for assignment in await _assignments(session, org, version.id, own):
            roles = sorted(
                role for role, ids in assignment.resources.items() if mine.intersection(ids)
            )
            out.append(
                MyAssignment(
                    **assignment.model_dump(),
                    version_id=version.id,
                    schedule_id=version.schedule_id,
                    schedule_name=schedule_name,
                    roles=roles,
                )
            )
    return sorted(out, key=lambda a: (a.start_at, str(a.activity_id)))
