import hashlib
from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import Conflict, NotFound, PayloadTooLarge, Unprocessable, field_error
from cartlyf_api.imports import repository as repo
from cartlyf_api.imports.csv_table import CsvError, CsvTable, parse_csv
from cartlyf_api.imports.demands_import import run_demand_import
from cartlyf_api.imports.models import ImportJob
from cartlyf_api.imports.resources_import import run_resource_import
from cartlyf_api.imports.schemas import (
    DemandMapping,
    DryRunRequest,
    ImportCreate,
    ImportKind,
    ImportReport,
    ImportResponse,
    ImportStatus,
    ResourceMapping,
)
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.settings import Settings
from cartlyf_api.storage import ObjectStore, org_object_key, owned_by


def job_response(job: ImportJob) -> ImportResponse:
    return ImportResponse(
        id=job.id,
        kind=cast(ImportKind, job.kind),
        status=cast(ImportStatus, job.status),
        filename=job.filename,
        resource_type_id=job.resource_type_id,
        schedule_id=job.schedule_id,
        columns=[str(c) for c in job.columns] if job.columns is not None else None,
        size_bytes=job.size_bytes,
        report=ImportReport.model_validate(job.report) if job.report else None,
        created_at=job.created_at,
        committed_at=job.committed_at,
    )


async def job_of(session: AsyncSession, principal: Principal, import_id: UUID) -> ImportJob:
    job = await repo.get_job(session, principal.organisation_id, import_id)
    if job is None:
        raise NotFound("Unknown import")
    return job


async def read_limited(chunks: AsyncIterator[bytes], limit: int) -> bytes:
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        if len(buffer) > limit:
            raise PayloadTooLarge(f"The file is larger than {limit} bytes")
    return bytes(buffer)


async def load_table(
    store: ObjectStore, settings: Settings, job: ImportJob, organisation_id: UUID
) -> CsvTable:
    # Storage has no RLS: the key prefix is re-checked against the caller's org before every read.
    if job.object_key is None or not owned_by(job.object_key, organisation_id):
        raise NotFound("The import has no file")
    return parse_csv(await store.get(job.object_key), settings.import_max_rows)


async def create_import(
    session: AsyncSession, principal: Principal, body: ImportCreate
) -> ImportResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    if body.resource_type_id is not None and (
        await resources_repo.get_type(session, org, body.resource_type_id) is None
    ):
        raise NotFound("Unknown resource type")
    if body.schedule_id is not None and (
        await schedules_repo.get_schedule(session, org, body.schedule_id) is None
    ):
        raise NotFound("Unknown schedule")
    import_id = uuid4()
    await repo.insert_job(
        session,
        {
            "id": import_id,
            "organisation_id": org,
            "kind": body.kind,
            "status": "awaiting_file",
            "resource_type_id": body.resource_type_id,
            "schedule_id": body.schedule_id,
            "filename": body.filename,
            "created_by": principal.user_id,
        },
    )
    await record_change(
        session, principal, "import.created", "import_job", import_id, {"kind": body.kind}
    )
    return await get_import(session, principal, import_id)


async def get_import(
    session: AsyncSession, principal: Principal, import_id: UUID
) -> ImportResponse:
    principal.require(Permission.CONFIG_READ)
    return job_response(await job_of(session, principal, import_id))


async def list_imports(session: AsyncSession, principal: Principal) -> list[ImportResponse]:
    principal.require(Permission.CONFIG_READ)
    return [job_response(job) for job in await repo.list_jobs(session, principal.organisation_id)]


async def upload_file(
    session: AsyncSession,
    store: ObjectStore,
    settings: Settings,
    principal: Principal,
    import_id: UUID,
    chunks: AsyncIterator[bytes],
) -> ImportResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    job = await job_of(session, principal, import_id)
    if job.status == "committed":
        raise Conflict("This import is already committed")
    data = await read_limited(chunks, settings.import_max_bytes)
    try:
        table = parse_csv(data, settings.import_max_rows)
    except CsvError as exc:
        raise Unprocessable([field_error(("body",), str(exc))]) from exc
    key = org_object_key(org, "imports", str(import_id), "source.csv")
    await store.put(key, data, "text/csv")
    await repo.update_job(
        session,
        org,
        import_id,
        {
            "status": "uploaded",
            "object_key": key,
            "size_bytes": len(data),
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "columns": list(table.columns),
            "mapping": None,
            "report": None,
        },
    )
    await record_change(
        session,
        principal,
        "import.uploaded",
        "import_job",
        import_id,
        {"bytes": len(data), "rows": len(table.rows)},
    )
    return await get_import(session, principal, import_id)


async def download_file(
    session: AsyncSession, store: ObjectStore, principal: Principal, import_id: UUID
) -> tuple[str, bytes]:
    principal.require(Permission.CONFIG_READ)
    job = await job_of(session, principal, import_id)
    if job.object_key is None or not owned_by(job.object_key, principal.organisation_id):
        raise NotFound("The import has no file")
    return job.filename, await store.get(job.object_key)


async def _run(
    session: AsyncSession,
    principal: Principal,
    job: ImportJob,
    table: CsvTable,
    mapping: ResourceMapping | DemandMapping,
    *,
    commit: bool,
) -> ImportReport:
    if mapping.kind != job.kind:
        message = f"this is a {job.kind} import"
        raise Unprocessable([field_error(("body", "mapping", "kind"), message)])
    if isinstance(mapping, DemandMapping):
        return await run_demand_import(session, principal, job, table, mapping, commit=commit)
    return await run_resource_import(session, principal, job, table, mapping, commit=commit)


async def dry_run(
    session: AsyncSession,
    store: ObjectStore,
    settings: Settings,
    principal: Principal,
    import_id: UUID,
    body: DryRunRequest,
) -> ImportResponse:
    principal.require(Permission.CONFIG_MANAGE)
    job = await job_of(session, principal, import_id)
    if job.status == "committed":
        raise Conflict("This import is already committed")
    table = await load_table(store, settings, job, principal.organisation_id)
    report = await _run(session, principal, job, table, body.mapping, commit=False)
    await repo.update_job(
        session,
        principal.organisation_id,
        import_id,
        {
            "mapping": body.mapping.model_dump(mode="json"),
            "report": report.model_dump(mode="json"),
            "status": "validated" if report.valid else "invalid",
        },
    )
    return await get_import(session, principal, import_id)


async def commit(
    session: AsyncSession,
    store: ObjectStore,
    settings: Settings,
    principal: Principal,
    import_id: UUID,
) -> ImportResponse:
    principal.require(Permission.CONFIG_MANAGE)
    job = await job_of(session, principal, import_id)
    if job.status != "validated" or job.mapping is None:
        raise Conflict("Run a dry run without errors before committing")
    table = await load_table(store, settings, job, principal.organisation_id)
    mapping = DryRunRequest.model_validate({"mapping": job.mapping}).mapping
    report = await _run(session, principal, job, table, mapping, commit=True)
    if not report.valid:
        # Raising rolls back the request transaction: nothing from this commit is written.
        raise Conflict(
            "The data changed since the dry run; nothing was imported",
            report=report.model_dump(mode="json"),
        )
    await repo.update_job(
        session,
        principal.organisation_id,
        import_id,
        {
            "status": "committed",
            "committed_at": func.now(),
            "report": report.model_dump(mode="json"),
        },
    )
    await record_change(
        session,
        principal,
        "import.committed",
        "import_job",
        import_id,
        {"kind": job.kind, "created": report.created},
    )
    return await get_import(session, principal, import_id)
