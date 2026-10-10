from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from cartlyf_api.auth.permissions import Role


def _distinct_sorted(roles: list[Role]) -> list[Role]:
    return sorted(set(roles))


Roles = Annotated[list[Role], Field(min_length=1), AfterValidator(_distinct_sorted)]


class InvitationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "kato@example.com", "name": "Kato M.", "roles": ["planner"]}]
        }
    )

    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    roles: Roles


class InvitationResponse(BaseModel):
    membership_id: UUID


class RolesUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"roles": ["planner", "member"]}]})

    roles: Roles


class MemberResponse(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    name: str
    status: str
    roles: list[Role]
