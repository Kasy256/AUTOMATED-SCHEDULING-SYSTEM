from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cartlyf_api.errors import Forbidden


class Role(StrEnum):
    ORG_ADMIN = "org_admin"
    PLANNER = "planner"
    MEMBER = "member"
    VIEWER = "viewer"


class Permission(StrEnum):
    MEMBERS_READ = "members.read"
    MEMBERS_MANAGE = "members.manage"
    CONFIG_READ = "config.read"
    CONFIG_MANAGE = "config.manage"
    SOLVES_RUN = "solves.run"
    VERSIONS_READ = "versions.read"
    VERSIONS_PUBLISH = "versions.publish"


_ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.ORG_ADMIN: frozenset(Permission),
    Role.PLANNER: frozenset(
        {
            Permission.MEMBERS_READ,
            Permission.CONFIG_READ,
            Permission.CONFIG_MANAGE,
            Permission.SOLVES_RUN,
            Permission.VERSIONS_READ,
            Permission.VERSIONS_PUBLISH,
        }
    ),
    Role.MEMBER: frozenset(),
    Role.VIEWER: frozenset({Permission.CONFIG_READ, Permission.VERSIONS_READ}),
}


def permissions_for(roles: Iterable[Role]) -> frozenset[Permission]:
    return frozenset[Permission]().union(*(_ROLE_PERMISSIONS[role] for role in roles))


@dataclass(frozen=True)
class Principal:
    """The authenticated caller acting within one organisation."""

    user_id: UUID
    organisation_id: UUID
    roles: frozenset[Role]
    via_platform_admin: bool = False

    def has(self, permission: Permission) -> bool:
        return permission in permissions_for(self.roles)

    def require(self, permission: Permission) -> None:
        if not self.has(permission):
            raise Forbidden()
