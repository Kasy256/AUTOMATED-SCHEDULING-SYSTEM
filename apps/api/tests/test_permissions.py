from itertools import combinations
from uuid import uuid4

import pytest

from cartlyf_api.auth.permissions import Permission, Principal, Role, permissions_for
from cartlyf_api.errors import Forbidden

ALL_ROLE_SETS = [frozenset(c) for n in range(len(Role) + 1) for c in combinations(Role, n)]


def test_AUTH_04_permissions_are_union_of_roles() -> None:
    for roles in ALL_ROLE_SETS:
        expected = frozenset[Permission]().union(*(permissions_for([r]) for r in roles))
        assert permissions_for(roles) == expected


def test_role_capabilities() -> None:
    assert permissions_for([Role.ORG_ADMIN]) == frozenset(Permission)
    planner = {
        Permission.MEMBERS_READ,
        Permission.CONFIG_READ,
        Permission.CONFIG_MANAGE,
        Permission.SOLVES_RUN,
        Permission.VERSIONS_READ,
        Permission.VERSIONS_PUBLISH,
    }
    assert permissions_for([Role.PLANNER]) == planner
    assert permissions_for([Role.MEMBER]) == frozenset()
    assert permissions_for([Role.VIEWER]) == {Permission.CONFIG_READ, Permission.VERSIONS_READ}
    assert permissions_for([Role.MEMBER, Role.PLANNER]) == planner


def test_principal_require() -> None:
    planner = Principal(uuid4(), uuid4(), frozenset({Role.PLANNER}))
    planner.require(Permission.MEMBERS_READ)
    with pytest.raises(Forbidden):
        planner.require(Permission.MEMBERS_MANAGE)


def test_principal_has() -> None:
    viewer = Principal(uuid4(), uuid4(), frozenset({Role.VIEWER}))
    assert viewer.has(Permission.VERSIONS_READ)
    assert not viewer.has(Permission.SOLVES_RUN)
