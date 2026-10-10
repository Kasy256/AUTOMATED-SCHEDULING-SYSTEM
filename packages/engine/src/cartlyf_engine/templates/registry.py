from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import JsonValue, ValidationError

from cartlyf_engine.templates import (
    balance,
    capacity_fit,
    day_distribution,
    fairness,
    max_consecutive,
    max_load,
    min_load,
    min_rest,
    minimize_gaps,
    precedence,
    preference,
    same_time,
    spread,
    stability,
)
from cartlyf_engine.templates.spec import TemplateSpec

_MODULES = (
    capacity_fit, max_load, min_load, min_rest, max_consecutive, spread, same_time,
    precedence, preference, minimize_gaps, balance, fairness, day_distribution, stability,
)  # fmt: skip
REGISTRY: Mapping[tuple[str, int], TemplateSpec] = MappingProxyType(
    {(m.SPEC.key, m.SPEC.version): m.SPEC for m in _MODULES}
)


class UnknownTemplate(LookupError):
    def __init__(self, message: str, field: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class InstanceProblem:
    loc: tuple[str | int, ...]
    msg: str
    type: str


class InvalidInstance(ValueError):
    def __init__(self, problems: list[InstanceProblem]) -> None:
        super().__init__("; ".join(f"{'.'.join(map(str, p.loc))}: {p.msg}" for p in problems))
        self.problems = problems


def get_template(key: str, version: int) -> TemplateSpec:
    spec = REGISTRY.get((key, version))
    if spec is not None:
        return spec
    if any(k == key for k, _ in REGISTRY):
        raise UnknownTemplate(f"{key} has no version {version}", "template_version")
    raise UnknownTemplate(f"unknown template '{key}'", "template_key")


def validate_instance(
    key: str, version: int, params: Mapping[str, object], *, hard: bool, weight: int
) -> dict[str, JsonValue]:
    """Validate a constraint instance against its template; returns the normalised params."""
    try:
        spec = get_template(key, version)
    except UnknownTemplate as exc:
        raise InvalidInstance(
            [InstanceProblem((exc.field,), str(exc), "unknown_template")]
        ) from exc
    problems: list[InstanceProblem] = []
    normalised: dict[str, JsonValue] = {}
    try:
        normalised = spec.params_model.model_validate(params).model_dump(mode="json")
    except ValidationError as exc:
        problems += [
            InstanceProblem(("params", *e["loc"]), e["msg"], e["type"]) for e in exc.errors()
        ]
    if hard and spec.soft_only:
        problems.append(InstanceProblem(("hard",), f"'{key}' can only be soft", "soft_only"))
    if not hard and weight < 1:
        problems.append(
            InstanceProblem(("weight",), "a soft rule needs a weight of at least 1", "weight")
        )
    if problems:
        raise InvalidInstance(problems)
    return normalised
