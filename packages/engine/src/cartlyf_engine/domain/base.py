from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

KEY_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"

Id = Annotated[str, StringConstraints(min_length=1, max_length=100)]
Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
