from fastapi import Response

from cartlyf_api.settings import Settings

REFRESH_COOKIE = "cartlyf_refresh"
# Only the auth endpoints ever receive the refresh token.
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, settings: Settings, raw: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86400,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
