from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response

from cartlyf_api.app_state import object_store_of, settings_of
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.imports import service
from cartlyf_api.imports.schemas import DryRunRequest, ImportCreate, ImportResponse
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["imports"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_ONE = {**_READ, 404: problem_response("Not found")}
_WRITE = {**_ONE, 409: problem_response("Conflict"), 422: problem_response("Invalid")}
# The upload is a raw text/csv body, read as a stream so the size limit applies while reading.
_CSV_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.get("/imports", response_model=list[ImportResponse], responses=_READ)
async def list_imports(session: DbSession, principal: CurrentPrincipal) -> list[ImportResponse]:
    return await service.list_imports(session, principal)


@router.post("/imports", status_code=201, response_model=ImportResponse, responses=_WRITE)
async def create_import(
    body: ImportCreate, session: DbSession, principal: CurrentPrincipal
) -> ImportResponse:
    return await service.create_import(session, principal, body)


@router.get("/imports/{import_id}", response_model=ImportResponse, responses=_ONE)
async def get_import(
    import_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ImportResponse:
    return await service.get_import(session, principal, import_id)


@router.put(
    "/imports/{import_id}/file",
    response_model=ImportResponse,
    responses={**_WRITE, 413: problem_response("File too large")},
    openapi_extra=_CSV_BODY,
)
async def upload_import_file(
    import_id: UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> ImportResponse:
    return await service.upload_file(
        session,
        object_store_of(request),
        settings_of(request),
        principal,
        import_id,
        request.stream(),
    )


@router.get(
    "/imports/{import_id}/file",
    response_class=Response,
    responses={**_ONE, 200: {"content": {"text/csv": {}}, "description": "The uploaded file"}},
)
async def download_import_file(
    import_id: UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> Response:
    filename, data = await service.download_file(
        session, object_store_of(request), principal, import_id
    )
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    return Response(
        data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.post("/imports/{import_id}/dry-run", response_model=ImportResponse, responses=_WRITE)
async def dry_run_import(
    import_id: UUID,
    body: DryRunRequest,
    request: Request,
    session: DbSession,
    principal: CurrentPrincipal,
) -> ImportResponse:
    return await service.dry_run(
        session, object_store_of(request), settings_of(request), principal, import_id, body
    )


@router.post("/imports/{import_id}/commit", response_model=ImportResponse, responses=_WRITE)
async def commit_import(
    import_id: UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> ImportResponse:
    return await service.commit(
        session, object_store_of(request), settings_of(request), principal, import_id
    )
