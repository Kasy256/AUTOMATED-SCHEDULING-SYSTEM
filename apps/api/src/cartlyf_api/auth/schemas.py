from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from cartlyf_api.auth.permissions import Role

# SecretStr keeps passwords out of reprs, logs and validation errors.
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=256)]
LinkToken = Annotated[str, Field(min_length=1, max_length=4096)]
_EXAMPLE_TOKEN = "eyJhbGciOiJIUzI1NiJ9.e30.signature"


class SignupRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "amina@example.com",
                    "name": "Amina N.",
                    "password": "correct horse battery",
                    "organisation_name": "Kampala Clinic",
                    "timezone": "Africa/Kampala",
                }
            ]
        }
    )

    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    password: NewPassword
    organisation_name: str = Field(min_length=1, max_length=200)
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("unknown IANA timezone")
        return value


class TokenRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"token": _EXAMPLE_TOKEN}]})

    token: LinkToken


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "amina@example.com", "password": "correct horse battery"}]
        }
    )

    email: EmailStr
    password: SecretStr = Field(max_length=256)


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"token": _EXAMPLE_TOKEN, "password": "correct horse battery"}]
        }
    )

    token: LinkToken
    password: NewPassword


class SwitchOrganisationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"organisation_id": "0b8a6f7e-3c1d-4f7a-9a51-1f2b3c4d5e6f"}]
        }
    )

    organisation_id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    organisation_id: UUID | None


class OrganisationSummary(BaseModel):
    organisation_id: UUID
    name: str


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    name: str
    organisation_id: UUID | None
    roles: list[Role]
    platform_admin_session: bool
    organisations: list[OrganisationSummary]
