from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.constraints.schemas import ConstraintWrite, ScopeWrite
from cartlyf_api.constraints.service import create_constraint
from cartlyf_api.errors import Conflict
from cartlyf_api.industry_templates.service import get_template
from cartlyf_api.resources.attribute_schema import AttributeSchema
from cartlyf_api.resources.schemas import ResourceTypeCreate
from cartlyf_api.resources.service import create_type, list_types
from cartlyf_api.schedules.schemas import (
    ScheduleCreate,
    ScheduleResponse,
    SlotTemplateWrite,
    horizon_errors,
)
from cartlyf_api.schedules.service import create_schedule, create_slot_template
from cartlyf_api.types import Name, TimeZoneName
from cartlyf_engine.domain import Key


class ScheduleFromTemplate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "template_key": "education",
                    "name": "Term 1 2027",
                    "timezone": "Africa/Kampala",
                    "start_date": "2027-01-11",
                    "end_date": "2027-01-15",
                }
            ]
        },
    )

    template_key: Key
    name: Name
    timezone: TimeZoneName
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _horizon(self) -> Self:
        if errors := horizon_errors(self.start_date, self.end_date):
            raise ValueError(errors[0][1])
        return self


class ScheduleFromTemplateResponse(BaseModel):
    schedule: ScheduleResponse
    resource_type_ids: dict[str, UUID]
    slot_template_ids: dict[str, UUID]
    constraint_ids: list[UUID]


def _missing_attributes(existing: AttributeSchema, wanted: AttributeSchema) -> list[str]:
    """Template attributes the existing type lacks or defines differently; extras are fine."""
    have = {a.key: a for a in existing.attributes}
    return [
        a.key
        for a in wanted.attributes
        if (h := have.get(a.key)) is None
        or h.type != a.type
        or not set(a.enum_values or []) <= set(h.enum_values or [])
    ]


async def apply_template(
    session: AsyncSession, principal: Principal, body: ScheduleFromTemplate
) -> ScheduleFromTemplateResponse:
    """Create a schedule configured by an industry template, adding missing resource types.

    Runs in the request transaction, so a conflict part-way leaves nothing behind.
    """
    principal.require(Permission.CONFIG_MANAGE)
    template = await get_template(session, body.template_key)
    existing = {t.key: t for t in await list_types(session, principal)}
    type_ids: dict[str, UUID] = {}
    for rtype in template.resource_types:
        if (found := existing.get(rtype.key)) is not None:
            if found.kind != rtype.kind:
                raise Conflict(
                    f"Resource type '{rtype.key}' exists with kind '{found.kind}', "
                    f"the template needs '{rtype.kind}'"
                )
            if missing := _missing_attributes(found.attribute_schema, rtype.attribute_schema):
                raise Conflict(
                    f"Resource type '{rtype.key}' exists without the template's attributes: "
                    f"{', '.join(missing)}"
                )
            type_ids[rtype.key] = found.id
            continue
        created = await create_type(
            session, principal, ResourceTypeCreate.model_validate(rtype.model_dump())
        )
        type_ids[rtype.key] = created.id

    schedule = await create_schedule(
        session,
        principal,
        ScheduleCreate(
            name=body.name,
            timezone=body.timezone,
            start_date=body.start_date,
            end_date=body.end_date,
            day_parts=template.day_parts,
        ),
    )
    slot_ids: dict[str, UUID] = {}
    for slot_template in template.slot_templates:
        written = SlotTemplateWrite(name=slot_template.name, definition=slot_template.definition)
        slot_ids[slot_template.name] = (
            await create_slot_template(session, principal, schedule.id, written)
        ).id

    constraint_ids: list[UUID] = []
    for rule in template.constraints:
        scope = ScopeWrite(
            resource_type_ids=[type_ids[k] for k in rule.scope.resource_type_keys],
            tags=list(rule.scope.tags),
            attrs=list(rule.scope.attrs),
        )
        write = ConstraintWrite(
            name=rule.name,
            template_key=rule.template_key,
            template_version=rule.version,
            params=rule.params,
            scope=scope,
            hard=rule.hard,
            weight=rule.weight,
            enabled=rule.enabled,
        )
        constraint_ids.append((await create_constraint(session, principal, schedule.id, write)).id)

    await record_change(
        session,
        principal,
        "schedule.created_from_template",
        "schedule",
        schedule.id,
        {"template": f"{template.key}@v{template.version}"},
    )
    return ScheduleFromTemplateResponse(
        schedule=schedule,
        resource_type_ids=type_ids,
        slot_template_ids=slot_ids,
        constraint_ids=constraint_ids,
    )
