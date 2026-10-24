from typing import Literal

from pydantic import BaseModel, ConfigDict


class DbRole(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_user: str
    rolsuper: bool
    rolbypassrls: bool

    @property
    def is_safe(self) -> bool:
        return not (self.rolsuper or self.rolbypassrls)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: DbRole
