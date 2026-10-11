from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.demands import persist_demand
from cartlyf_api.activities.expansion import ExpansionError, expand_demand
from cartlyf_api.activities.schemas import DemandWrite
from cartlyf_api.auth.permissions import Principal
from cartlyf_api.errors import Conflict, NotFound, Unprocessable, field_error
from cartlyf_api.imports.csv_table import CsvTable, split_list
from cartlyf_api.imports.models import ImportJob
from cartlyf_api.imports.reports import missing_column_errors, report_of
from cartlyf_api.imports.schemas import DemandMapping, ImportReport, RowError
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.resources.attribute_schema import AttributeSchema, coerce_cell
from cartlyf_api.resources.models import ResourceType
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.schedules.schemas import SlotTemplateDefinition
from cartlyf_engine.precheck import precheck

_SPEC_FIELDS = ("sessions_per_week", "duration_minutes", "slot_labels")


def _locate(loc: Sequence[str | int], mapping: DemandMapping) -> str | None:
    """CSV column responsible for a DemandWrite validation or expansion error location.
    Discriminated-union errors carry the tag, e.g. ("spec", "session", "sessions_per_week")."""
    parts = list(loc)
    if parts[:1] == ["name"]:
        return mapping.name
    for field in _SPEC_FIELDS:
        if field in parts:
            return getattr(mapping, field)
    if "requirements" in parts:
        rest = parts[parts.index("requirements") + 1 :]
        if len(rest) >= 2 and isinstance(rest[0], int) and rest[0] < len(mapping.requirements):
            req = mapping.requirements[rest[0]]
            columns = {"tags": req.tags_column, "fixed_resource_ids": req.fixed_codes_column}
            return columns.get(str(rest[1]))
    return None


def _demand_from_row(
    line: int,
    record: Mapping[str, str],
    mapping: DemandMapping,
    codes: Mapping[str, UUID],
    types: Mapping[UUID, ResourceType],
) -> tuple[list[RowError], DemandWrite | None]:
    def cell(column: str | None) -> str:
        return record.get(column, "") if column else ""

    errors: list[RowError] = []
    spec: dict[str, object] = {"kind": mapping.demand_kind}
    if mapping.demand_kind == "session":
        spec["sessions_per_week"] = cell(mapping.sessions_per_week)
        if cell(mapping.duration_minutes):
            spec["duration_minutes"] = cell(mapping.duration_minutes)
    if cell(mapping.slot_labels):
        spec["slot_labels"] = split_list(cell(mapping.slot_labels))
    requirements: list[dict[str, object]] = []
    for req in mapping.requirements:
        requirement: dict[str, object] = {
            "role": req.role,
            "resource_type_id": req.resource_type_id,
            "count_min": req.count_min,
            "count_max": req.count_max,
            "hard": req.hard,
            "weight": req.weight,
            "tags": split_list(cell(req.tags_column)),
        }
        wanted = split_list(cell(req.fixed_codes_column))
        if unknown := [code for code in wanted if code not in codes]:
            # Codes are the planner's own identifiers, so naming them leaks nothing.
            message = f"Unknown resource codes: {', '.join(unknown)}"
            errors.append(RowError(row=line, column=req.fixed_codes_column, message=message))
        requirement["fixed_resource_ids"] = [codes[c] for c in wanted if c in codes]
        rtype = types.get(req.resource_type_id) if req.resource_type_id else None
        schema = (
            AttributeSchema.model_validate(rtype.attribute_schema) if rtype else AttributeSchema()
        )
        definitions = {d.key: d for d in schema.attributes}
        requirement["attrs"] = [
            {
                "attr": key,
                "op": "eq",
                "value": coerce_cell(definitions[key], cell(column))
                if key in definitions
                else cell(column),
            }
            for key, column in req.attribute_columns.items()
            if cell(column)
        ]
        requirements.append(requirement)
    spec["requirements"] = requirements
    try:
        body = DemandWrite.model_validate(
            {"name": cell(mapping.name), "slot_template_id": mapping.slot_template_id, "spec": spec}
        )
    except ValidationError as exc:
        errors += [
            RowError(row=line, column=_locate(e["loc"], mapping), message=e["msg"])
            for e in exc.errors()
        ]
        return errors, None
    return errors, body


def _mapping_columns(mapping: DemandMapping) -> dict[str, str | None]:
    columns: dict[str, str | None] = {
        "name": mapping.name,
        "sessions_per_week": mapping.sessions_per_week,
        "duration_minutes": mapping.duration_minutes,
        "slot_labels": mapping.slot_labels,
    }
    for i, req in enumerate(mapping.requirements):
        columns[f"requirements.{i}.tags_column"] = req.tags_column
        columns[f"requirements.{i}.fixed_codes_column"] = req.fixed_codes_column
        for key, column in req.attribute_columns.items():
            columns[f"requirements.{i}.attribute_columns.{key}"] = column
    return columns


async def run_demand_import(
    session: AsyncSession,
    principal: Principal,
    job: ImportJob,
    table: CsvTable,
    mapping: DemandMapping,
    *,
    commit: bool,
) -> ImportReport:
    """Validate every row, then write in a savepoint so the feasibility check sees the new
    demands; a dry run rolls the savepoint back."""
    org = principal.organisation_id
    schedule = None
    if job.schedule_id is not None:
        schedule = await schedules_repo.get_schedule(session, org, job.schedule_id)
    if schedule is None:
        raise Conflict("The import's schedule no longer exists")
    template = await schedules_repo.get_slot_template(
        session, org, schedule.id, mapping.slot_template_id
    )
    if template is None:
        raise NotFound("Unknown slot template")
    type_ids = {r.resource_type_id for r in mapping.requirements if r.resource_type_id}
    if await resources_repo.missing_type_ids(session, org, type_ids):
        raise NotFound("Unknown resource type")
    problems = missing_column_errors(_mapping_columns(mapping), table.columns)
    if mapping.demand_kind == "session" and mapping.sessions_per_week is None:
        problems.append(field_error(("body", "mapping", "sessions_per_week"), "Field required"))
    if problems:
        raise Unprocessable(problems)

    codes = await resources_repo.live_codes(session, org)
    types = await resources_repo.types_by_id(session, org)
    slots = SlotTemplateDefinition.model_validate(template.definition).slots
    horizon = schedule.horizon()
    errors: list[RowError] = []
    bodies: list[DemandWrite] = []
    for line, record in table.rows:
        row_errors, body = _demand_from_row(line, record, mapping, codes, types)
        if body is not None:
            try:
                expand_demand(body.name, body.spec, slots, horizon)
            except ExpansionError as exc:
                column = _locate(exc.loc, mapping)
                row_errors.append(RowError(row=line, column=column, message=str(exc)))
        errors += row_errors
        if body is not None and not row_errors:
            bodies.append(body)
    if errors:
        return report_of(len(table.rows), 0, errors)

    savepoint = await session.begin_nested()
    for body in bodies:
        await persist_demand(session, org, schedule, template, uuid4(), body, created=True)
    issues = precheck((await build_snapshot(session, org, schedule.id)).problem)
    if commit:
        await savepoint.commit()
    else:
        await savepoint.rollback()
    return report_of(len(table.rows), len(bodies), [], issues)
