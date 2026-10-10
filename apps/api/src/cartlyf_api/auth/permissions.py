from enum import StrEnum


class Role(StrEnum):
    ORG_ADMIN = "org_admin"
    PLANNER = "planner"
    MEMBER = "member"
    VIEWER = "viewer"
