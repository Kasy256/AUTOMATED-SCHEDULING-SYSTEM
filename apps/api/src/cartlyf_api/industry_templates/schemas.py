from importlib.resources import files
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from cartlyf_api.imports.schemas import Column, TermSplitPreset
from cartlyf_api.resources.attribute_schema import AttributeSchema
from cartlyf_api.schedules.schemas import DayParts, RequirementDefaults, SlotTemplateDefinition
from cartlyf_api.types import Name
from cartlyf_engine.domain import AttributePredicate, Key, ResourceKind, Tag
from cartlyf_engine.templates.registry import InvalidInstance, validate_instance

Text = Annotated[str, Field(min_length=1, max_length=1000)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TemplateResourceType(_Model):
    key: Key
    name: Name
    kind: ResourceKind
    attribute_schema: AttributeSchema = AttributeSchema()


class TemplateSlotTemplate(_Model):
    name: Name
    definition: SlotTemplateDefinition


class TemplateScope(_Model):
    """Like a constraint scope, but names resource types by key: ids exist only once applied."""

    resource_type_keys: list[Key] = Field(default_factory=list[str])
    tags: list[Tag] = Field(default_factory=list[str])
    attrs: list[AttributePredicate] = Field(default_factory=list[AttributePredicate])


class TemplateConstraint(_Model):
    name: Name
    template_key: Key
    version: PositiveInt
    params: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    scope: TemplateScope = TemplateScope()
    hard: bool
    weight: NonNegativeInt = 0
    enabled: bool = True

    @model_validator(mode="after")
    def _valid_rule(self) -> Self:
        try:
            params = validate_instance(
                self.template_key, self.version, self.params, hard=self.hard, weight=self.weight
            )
        except InvalidInstance as exc:
            raise ValueError(
                "; ".join(f"{'.'.join(map(str, p.loc))}: {p.msg}" for p in exc.problems)
            ) from exc
        # Frozen model: store the normalised params exactly as a constraint instance would.
        object.__setattr__(self, "params", params)
        return self


class TemplateRequirement(_Model):
    role: Key
    resource_type_key: Key
    count_min: NonNegativeInt = 1
    count_max: PositiveInt = 1
    count_from_fixed: bool = False
    fixed_codes_column: Column | None = None
    tags_column: Column | None = None
    attribute_columns: dict[Key, Column] = Field(default_factory=dict[str, str])


class TemplateDemandShape(_Model):
    """A preset for the demand import: which CSV columns feed which requirement."""

    kind: Literal["session", "coverage"]
    slot_template: Name
    name_column: Column
    sessions_per_week_column: Column | None = None
    weekly_minutes_column: Column | None = None
    requirements: list[TemplateRequirement] = Field(min_length=1)
    term_split: TermSplitPreset | None = None


class IndustryTemplateDefinition(_Model):
    key: Key
    version: PositiveInt
    name: Name
    description: Text
    resource_types: list[TemplateResourceType] = Field(min_length=1)
    day_parts: DayParts = DayParts()
    slot_templates: list[TemplateSlotTemplate] = Field(default_factory=list[TemplateSlotTemplate])
    demand_shape: TemplateDemandShape | None = None
    # Omitted from dumps when unset so earlier frozen template copies keep matching.
    requirement_defaults: RequirementDefaults | None = Field(
        default=None, exclude_if=lambda v: v is None
    )
    constraints: list[TemplateConstraint] = Field(default_factory=list[TemplateConstraint])

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        types = [t.key for t in self.resource_types]
        if len(set(types)) != len(types):
            raise ValueError("resource type keys must be unique")
        named = {k for c in self.constraints for k in c.scope.resource_type_keys}
        if self.demand_shape is not None:
            named |= {r.resource_type_key for r in self.demand_shape.requirements}
            slots = {s.name for s in self.slot_templates}
            if self.demand_shape.slot_template not in slots:
                raise ValueError(f"unknown slot template '{self.demand_shape.slot_template}'")
        if unknown := sorted(named - set(types)):
            raise ValueError(f"unknown resource types: {', '.join(unknown)}")
        windows = {p.name for p in self.day_parts.parts}
        for c in self.constraints:
            window = c.params.get("window")
            if isinstance(window, str) and window not in windows:
                raise ValueError(f"'{c.name}' names unknown day part '{window}'")
        return self


def load_packaged(key: str) -> IndustryTemplateDefinition:
    text = files("cartlyf_api.industry_templates").joinpath(f"data/{key}.json").read_text("utf-8")
    return IndustryTemplateDefinition.model_validate_json(text)
