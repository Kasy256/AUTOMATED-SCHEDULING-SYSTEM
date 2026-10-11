from collections.abc import Mapping, Sequence
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.permissions import Principal
from cartlyf_api.errors import Conflict, FieldError, Unprocessable, field_error
from cartlyf_api.imports.csv_table import CsvTable, split_list
from cartlyf_api.imports.models import ImportJob
from cartlyf_api.imports.reports import missing_column_errors, report_of
from cartlyf_api.imports.schemas import ImportReport, ResourceMapping, RowError
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.resources.attribute_schema import AttributeSchema, coerce_cell
from cartlyf_api.resources.schemas import ResourceCreate
from cartlyf_api.resources.service import resource_errors, resource_row

_FIELDS = ("code", "name", "tags", "capacity", "size", "concurrency")


def _column(loc: Sequence[str | int], mapping: ResourceMapping) -> str | None:
    if loc and loc[0] in _FIELDS:
        return getattr(mapping, str(loc[0]))
    if len(loc) > 1 and loc[0] == "attributes":
        return mapping.attributes.get(str(loc[1]))
    return None


def _row_values(
    record: Mapping[str, str], mapping: ResourceMapping, schema: AttributeSchema, type_id: UUID
) -> dict[str, object]:
    def cell(column: str | None) -> str:
        return record.get(column, "") if column else ""

    definitions = {d.key: d for d in schema.attributes}
    values: dict[str, object] = {
        "resource_type_id": type_id,
        "code": cell(mapping.code),
        "name": cell(mapping.name),
    }
    if mapping.tags:
        values["tags"] = split_list(cell(mapping.tags))
    for field in ("capacity", "size", "concurrency"):
        if (column := getattr(mapping, field)) and cell(column):
            values[field] = cell(column)
    values["attributes"] = {
        key: coerce_cell(definitions[key], cell(column))
        for key, column in mapping.attributes.items()
        if cell(column)
    }
    return values


def _mapping_errors(
    mapping: ResourceMapping, schema: AttributeSchema, columns: Sequence[str]
) -> list[FieldError]:
    known = {d.key for d in schema.attributes}
    mapped: dict[str, str | None] = {f: getattr(mapping, f) for f in _FIELDS}
    mapped |= {f"attributes.{key}": column for key, column in mapping.attributes.items()}
    return missing_column_errors(mapped, columns) + [
        field_error(("body", "mapping", "attributes", key), "Unknown attribute")
        for key in mapping.attributes
        if key not in known
    ]


async def run_resource_import(
    session: AsyncSession,
    principal: Principal,
    job: ImportJob,
    table: CsvTable,
    mapping: ResourceMapping,
    *,
    commit: bool,
) -> ImportReport:
    """Validate every row first; write only when no row has an error (and only on commit)."""
    org = principal.organisation_id
    rtype = None
    if job.resource_type_id is not None:
        rtype = await resources_repo.get_type(session, org, job.resource_type_id)
    if rtype is None:
        raise Conflict("The import's resource type no longer exists")
    schema = AttributeSchema.model_validate(rtype.attribute_schema)
    if problems := _mapping_errors(mapping, schema, table.columns):
        raise Unprocessable(problems)
    existing = await resources_repo.live_codes(session, org)
    first_seen: dict[str, int] = {}
    errors: list[RowError] = []
    rows: list[dict[str, object]] = []
    for line, record in table.rows:
        try:
            body = ResourceCreate.model_validate(_row_values(record, mapping, schema, rtype.id))
        except ValidationError as exc:
            errors += [
                RowError(row=line, column=_column(e["loc"], mapping), message=e["msg"])
                for e in exc.errors()
            ]
            continue
        found = resource_errors(rtype, body.attributes, body.capacity, body.size, loc_prefix=())
        errors += [
            RowError(row=line, column=_column(e["loc"], mapping), message=e["msg"]) for e in found
        ]
        if body.code in existing:
            message = "A resource with this code already exists"
            errors.append(RowError(row=line, column=mapping.code, message=message))
        elif body.code in first_seen:
            message = f"Duplicate code; first used on row {first_seen[body.code]}"
            errors.append(RowError(row=line, column=mapping.code, message=message))
        first_seen.setdefault(body.code, line)
        if not found:
            rows.append(resource_row(uuid4(), org, body))
    if errors:
        return report_of(len(table.rows), 0, errors)
    if commit:
        await resources_repo.insert_resources(session, rows)
    return report_of(len(table.rows), len(rows), [])
