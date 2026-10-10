from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import ClassVar, TypedDict

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

PROBLEM_JSON = "application/problem+json"
log = structlog.get_logger()


class Problem(BaseModel):
    """RFC 9457 problem details, for documenting error responses in OpenAPI."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None


def problem_response(description: str) -> dict[str, object]:
    return {
        "description": description,
        "content": {PROBLEM_JSON: {"schema": Problem.model_json_schema()}},
    }


def problem(
    status: int,
    title: str,
    detail: str | None = None,
    headers: Mapping[str, str] | None = None,
    **extra: object,
) -> JSONResponse:
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM_JSON)


class FieldError(TypedDict):
    loc: list[str | int]
    msg: str
    type: str


def field_error(loc: Sequence[str | int], msg: str, type_: str = "value_error") -> FieldError:
    return {"loc": list(loc), "msg": msg, "type": type_}


class DomainError(Exception):
    """Raised by services; mapped to a problem response by one handler."""

    status: ClassVar[int] = 400
    title: ClassVar[str] = "Bad Request"
    headers: ClassVar[Mapping[str, str] | None] = None

    def __init__(self, detail: str | None = None, **extra: object) -> None:
        super().__init__(detail)
        self.detail = detail
        self.extra = extra


class InvalidLink(DomainError):
    title = "Invalid or expired link"


class Unauthorized(DomainError):
    status = 401
    title = "Unauthorized"
    headers: ClassVar[Mapping[str, str] | None] = {"WWW-Authenticate": "Bearer"}


class Forbidden(DomainError):
    status = 403
    title = "Forbidden"


class NotFound(DomainError):
    status = 404
    title = "Not Found"


class Conflict(DomainError):
    status = 409
    title = "Conflict"


class Unprocessable(DomainError):
    status = 422
    title = "Unprocessable Content"

    def __init__(self, errors: list[FieldError], detail: str | None = None) -> None:
        super().__init__(detail, errors=errors)
        self.errors = errors


class PayloadTooLarge(DomainError):
    status = 413
    title = "Content Too Large"


class RateLimited(DomainError):
    status = 429
    title = "Too Many Requests"

    def __init__(self, retry_after: int) -> None:
        super().__init__()
        self.retry_after = retry_after


class ServiceUnavailable(DomainError):
    status = 503
    title = "Service Unavailable"


# Handlers take Exception (not a subclass) to match Starlette's handler type under pyright strict.
async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    title = HTTPStatus(exc.status_code).phrase
    detail = exc.detail if exc.detail != title else None
    return problem(exc.status_code, title, detail, exc.headers)


async def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    headers = dict(exc.headers or {})
    if isinstance(exc, RateLimited):
        headers["Retry-After"] = str(exc.retry_after)
    return problem(exc.status, exc.title, exc.detail, headers or None, **exc.extra)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only loc/msg/type: pydantic's "input" and "ctx" can echo secrets back to the client.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return problem(422, "Unprocessable Content", errors=errors)


async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", path=request.url.path, exc_info=exc)
    return problem(500, "Internal Server Error")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(Exception, _unhandled_error)
