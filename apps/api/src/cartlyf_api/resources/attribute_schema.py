from collections.abc import Mapping, Sequence
from typing import Annotated, Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from cartlyf_api.errors import FieldError, field_error
from cartlyf_engine.domain import Key

AttributeType = Literal["string", "integer", "number", "boolean", "enum", "tags"]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MAX_TEXT = 1000
_TRUE, _FALSE = {"true", "yes", "1"}, {"false", "no", "0"}


class AttributeDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Key
    label: Label | None = None
    type: AttributeType
    required: bool = False
    enum_values: list[Label] | None = None

    @model_validator(mode="after")
    def _enum_values_fit_type(self) -> Self:
        if self.type == "enum":
            values = self.enum_values or []
            if not values or len(set(values)) != len(values):
                raise ValueError("enum attributes need distinct enum_values")
        elif self.enum_values is not None:
            raise ValueError("enum_values is only for enum attributes")
        return self


class AttributeSchema(BaseModel):
    """Version 1 of a resource type's attribute schema (a small JSON-schema subset)."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    attributes: list[AttributeDef] = Field(default_factory=list[AttributeDef], max_length=100)

    @model_validator(mode="after")
    def _unique_keys(self) -> Self:
        keys = [a.key for a in self.attributes]
        if len(set(keys)) != len(keys):
            raise ValueError("attribute keys must be unique")
        return self


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _type_error(definition: AttributeDef, value: object) -> str | None:
    match definition.type:
        case "string":
            ok = isinstance(value, str) and len(value) <= MAX_TEXT
            return None if ok else f"must be text of at most {MAX_TEXT} characters"
        case "integer":
            return None if _is_int(value) else "must be a whole number"
        case "number":
            ok = _is_int(value) or isinstance(value, float)
            return None if ok else "must be a number"
        case "boolean":
            return None if isinstance(value, bool) else "must be true or false"
        case "enum":
            allowed = definition.enum_values or []
            ok = isinstance(value, str) and value in allowed
            return None if ok else f"must be one of: {', '.join(allowed)}"
        case "tags":
            items = cast(list[object], value) if isinstance(value, list) else None
            ok = items is not None and all(isinstance(t, str) and t for t in items)
            ok = ok and items is not None and len(set(map(str, items))) == len(items)
            return None if ok else "must be a list of distinct non-empty strings"


def validate_attributes(
    schema: AttributeSchema, values: Mapping[str, object], loc: Sequence[str | int]
) -> list[FieldError]:
    """Field-level errors for `values` against `schema`; never echoes the values."""
    definitions = {d.key: d for d in schema.attributes}
    errors = [
        field_error((*loc, key), "Unknown attribute", "extra_forbidden")
        for key in sorted(values.keys() - definitions.keys())
    ]
    for definition in schema.attributes:
        if definition.key not in values:
            if definition.required:
                errors.append(field_error((*loc, definition.key), "Field required", "missing"))
            continue
        if message := _type_error(definition, values[definition.key]):
            errors.append(field_error((*loc, definition.key), message))
    return errors


def coerce_cell(definition: AttributeDef, cell: str) -> object:
    """Convert a CSV cell to the attribute's type; unconvertible text is returned as-is so
    `validate_attributes` reports it with the normal message."""
    text = cell.strip()
    match definition.type:
        case "integer":
            return int(text) if text.lstrip("-").isdigit() else text
        case "number":
            try:
                return float(text) if any(c in text for c in ".eE") else int(text)
            except ValueError:
                return text
        case "boolean":
            lowered = text.lower()
            return True if lowered in _TRUE else False if lowered in _FALSE else text
        case "tags":
            return [part.strip() for part in text.split(";") if part.strip()]
        case "string" | "enum":
            return text
