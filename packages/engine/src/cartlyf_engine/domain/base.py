from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

KEY_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"

Id = Annotated[str, StringConstraints(min_length=1, max_length=100)]
Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

# Display hints for the rule builder (which list a picker offers); validation is unchanged.
SeriesId = Annotated[Id, Field(json_schema_extra={"x-ref": "series"})]
ResourceId = Annotated[Id, Field(json_schema_extra={"x-ref": "resource"})]
WindowKey = Annotated[Key, Field(json_schema_extra={"x-ref": "window"})]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
