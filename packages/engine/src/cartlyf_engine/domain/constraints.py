from typing import Self

from pydantic import Field, JsonValue, NonNegativeInt, PositiveInt, model_validator

from cartlyf_engine.domain.base import Frozen, Id, Key, Tag
from cartlyf_engine.domain.filters import AttributePredicate


class Scope(Frozen):
    """Which resources/activities an instance applies to; empty means everything."""

    resource_type_keys: tuple[Key, ...] = ()
    tags: tuple[Tag, ...] = ()
    attrs: tuple[AttributePredicate, ...] = ()
    resource_ids: tuple[Id, ...] = ()
    series_ids: tuple[Id, ...] = ()


class ConstraintInstance(Frozen):
    id: Id
    template_key: Key
    version: PositiveInt
    params: dict[str, JsonValue] = Field(default_factory=dict)
    scope: Scope = Scope()
    hard: bool
    weight: NonNegativeInt = 0

    @model_validator(mode="after")
    def _valid_for_template(self) -> Self:
        # Imported here: the registry's template modules import domain types.
        from cartlyf_engine.templates.registry import validate_instance

        validate_instance(
            self.template_key, self.version, self.params, hard=self.hard, weight=self.weight
        )
        return self
