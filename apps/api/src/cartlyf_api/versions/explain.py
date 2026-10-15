"""Explanations of a version: why an assignment is where it is, and what a move would break."""

import asyncio
from datetime import timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import NotFound, Unprocessable, field_error
from cartlyf_api.schedules.time_grid import floor_minutes
from cartlyf_api.versions.schemas import (
    AlternativeOut,
    BindingRule,
    ExplanationOut,
    MoveCheckOut,
    MoveRequest,
    PenaltyChangeOut,
    RuleBreak,
)
from cartlyf_api.versions.service import require_version
from cartlyf_api.versions.state import VersionState, engine_resources, load_state
from cartlyf_engine.domain import Assignment
from cartlyf_engine.explain import explain_assignment
from cartlyf_engine.moves import MoveCheck, MoveChecker


def _check_out(check: MoveCheck) -> MoveCheckOut:
    return MoveCheckOut(
        valid=check.valid,
        broken=[
            RuleBreak(
                constraint_id=b.constraint_id,
                rule=b.rule,
                message=b.message,
                activity_ids=[UUID(i) for i in b.activity_ids],
                resource_ids=[UUID(i) for i in b.resource_ids],
            )
            for b in check.broken
        ],
        penalties=[
            PenaltyChangeOut(
                constraint_id=p.constraint_id, rule=p.rule, before=p.before, after=p.after
            )
            for p in check.penalties
        ],
    )


def _move(state: VersionState, body: MoveRequest) -> Assignment:
    if str(body.activity_id) not in {a.id for a in state.problem.activities}:
        raise NotFound("Unknown activity")
    known = {r.id for r in state.problem.resources}
    if any(str(r) not in known for ids in body.resources.values() for r in ids):
        raise NotFound("Unknown resource")
    start = floor_minutes(state.run.horizon_origin, body.start_at)
    if start < 0:
        raise Unprocessable([field_error(("body", "start_at"), "is before the schedule starts")])
    return Assignment(
        activity_id=str(body.activity_id), start=start, resources=engine_resources(body.resources)
    )


async def validate_move(
    session: AsyncSession, principal: Principal, version_id: UUID, body: MoveRequest
) -> MoveCheckOut:
    principal.require(Permission.SOLVES_RUN)
    org = principal.organisation_id
    state = await load_state(session, org, await require_version(session, org, version_id))
    move = _move(state, body)
    checker = MoveChecker(state.problem, list(state.assignments.values()))
    return _check_out(await asyncio.to_thread(checker.check, move))


async def explain(
    session: AsyncSession, principal: Principal, version_id: UUID, activity_id: UUID
) -> ExplanationOut:
    principal.require(Permission.VERSIONS_READ)
    org = principal.organisation_id
    state = await load_state(session, org, await require_version(session, org, version_id))
    if str(activity_id) not in state.assignments:
        raise NotFound("The activity is not placed in this version")
    why = await asyncio.to_thread(
        explain_assignment, state.problem, list(state.assignments.values()), str(activity_id)
    )
    origin = state.run.horizon_origin
    return ExplanationOut(
        activity_id=activity_id,
        binding=[BindingRule.model_validate(b.model_dump()) for b in why.binding],
        alternatives=[
            AlternativeOut(
                start_at=origin + timedelta(minutes=a.start),
                resources={role: [UUID(i) for i in ids] for role, ids in a.resources.items()},
                check=_check_out(a.check),
            )
            for a in why.alternatives
        ],
    )
