"""Planner actions that create or change version state: draft edits, publish, archive."""

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.email import messages
from cartlyf_api.email.outbox import QueuedEmail, enqueue
from cartlyf_api.errors import Conflict, FieldError, NotFound, Unprocessable, field_error
from cartlyf_api.fairness import service as fairness_ledger
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.schedules.time_grid import floor_minutes
from cartlyf_api.settings import Settings
from cartlyf_api.versions import repository
from cartlyf_api.versions.notify import affected_users
from cartlyf_api.versions.persist import lock_schedule, write_version
from cartlyf_api.versions.schemas import DraftRequest, VersionDetail
from cartlyf_api.versions.service import require_version, version_detail
from cartlyf_api.versions.state import engine_resources, load_state
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Assignment


async def create_draft(
    session: AsyncSession,
    settings: Settings,
    principal: Principal,
    version_id: UUID,
    body: DraftRequest,
) -> VersionDetail:
    """A new draft: the parent with `body.changes` applied, verified by the checker."""
    principal.require(Permission.SOLVES_RUN)
    org = principal.organisation_id
    parent = await require_version(session, org, version_id)
    state = await load_state(session, org, parent)
    run, problem = state.run, state.problem
    activities = {a.id: a for a in problem.activities}
    resource_ids = {r.id for r in problem.resources}
    for change in body.changes:
        if str(change.activity_id) not in activities:
            raise NotFound("Unknown activity")
        if any(str(r) not in resource_ids for ids in change.resources.values() for r in ids):
            raise NotFound("Unknown resource")
    if len(body.changes) > settings.draft_max_changes:
        raise Unprocessable(
            [field_error(("body", "changes"), f"must have at most {settings.draft_max_changes}")]
        )

    placed: dict[str, Assignment] = {}
    errors: list[FieldError] = []
    seen: set[str] = set()
    for i, change in enumerate(body.changes):
        activity_id = str(change.activity_id)
        if activity_id in seen:
            errors.append(field_error(("body", "changes", i, "activity_id"), "is a duplicate"))
            continue
        seen.add(activity_id)
        start = floor_minutes(run.horizon_origin, change.start_at)
        if start not in activities[activity_id].candidate_starts:
            errors.append(
                field_error(("body", "changes", i, "start_at"), "is not a candidate start")
            )
            continue
        placed[activity_id] = Assignment(
            activity_id=activity_id,
            start=start,
            resources=engine_resources(change.resources),
        )
    if errors:
        raise Unprocessable(errors)

    assignments = list((state.assignments | placed).values())
    score = await asyncio.to_thread(check, problem, assignments)
    if score.hard_violations > 0:
        raise Unprocessable(
            [
                field_error(("body", "changes"), f"{v.constraint_id}: {v.message}")
                for v in score.violations
            ],
            "The edit breaks hard rules",
        )
    new_id = await write_version(
        session,
        org=org,
        schedule_id=parent.schedule_id,
        run=run,
        parent_id=parent.id,
        solver_status="EDITED",
        assignments=assignments,
        score=score,
        origin=run.horizon_origin,
        problem=problem,
        user_id=principal.user_id,
    )
    await record_change(
        session,
        principal,
        "version.draft_created",
        "solution_version",
        new_id,
        {"parent_version_id": str(parent.id)},
    )
    return await version_detail(session, org, await require_version(session, org, new_id))


async def publish(
    session: AsyncSession, settings: Settings, principal: Principal, version_id: UUID
) -> tuple[VersionDetail, list[QueuedEmail]]:
    """Publish a draft, archiving the schedule's previous published version; queue member emails."""
    principal.require(Permission.VERSIONS_PUBLISH)
    org = principal.organisation_id
    found = await require_version(session, org, version_id)
    schedule = await schedules_repo.get_schedule(session, org, found.schedule_id)
    if schedule is None:
        raise NotFound("Unknown schedule")
    await lock_schedule(session, schedule.id)
    # The row lock also waits out any assignment insert racing the draft-only trigger.
    version = await require_version(session, org, version_id, for_update=True)
    if version.status != "draft":
        raise Conflict("Only drafts can be published")
    previous = await repository.published_version_id(session, org, version.schedule_id)
    if previous is not None:
        await repository.mark_archived(session, org, previous)
    await repository.mark_published(session, org, version.id, principal.user_id)
    await session.refresh(version)
    await fairness_ledger.record_published(session, org, version)

    counts = await affected_users(session, org, version.id, previous)
    addresses = await orgs_repo.active_member_emails(session, org, counts.keys())
    queued = [
        await enqueue(
            session,
            user_id,
            messages.schedule_published(
                settings, address, schedule.name, schedule.id, version.id, counts[user_id]
            ),
        )
        for user_id, address in addresses.items()
    ]
    await record_change(
        session,
        principal,
        "version.published",
        "solution_version",
        version.id,
        {"previous_version_id": str(previous) if previous else None, "recipients": len(queued)},
    )
    return await version_detail(session, org, version), queued


async def archive(session: AsyncSession, principal: Principal, version_id: UUID) -> VersionDetail:
    principal.require(Permission.VERSIONS_PUBLISH)
    org = principal.organisation_id
    version = await require_version(session, org, version_id, for_update=True)
    if version.status == "archived":
        raise Conflict("Version is already archived")
    if version.status == "published":
        await fairness_ledger.clear_schedule(session, org, version.schedule_id)
    await repository.mark_archived(session, org, version.id)
    await session.refresh(version)
    await record_change(session, principal, "version.archived", "solution_version", version.id)
    return await version_detail(session, org, version)
