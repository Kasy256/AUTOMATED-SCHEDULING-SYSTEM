import pytest
from pydantic import ValidationError

from cartlyf_engine.domain import ConstraintInstance
from cartlyf_engine.templates.registry import (
    REGISTRY,
    InvalidInstance,
    UnknownTemplate,
    get_template,
    validate_instance,
)

V1_KEYS = {
    "capacity_fit", "max_load", "min_load", "min_rest", "max_consecutive", "spread",
    "same_time", "precedence", "preference", "minimize_gaps", "balance", "fairness",
    "day_distribution", "stability",
}  # fmt: skip
SOFT_ONLY = {"preference", "minimize_gaps", "balance", "fairness", "day_distribution", "stability"}


def test_DOM_05_registry_holds_every_v1_template() -> None:
    assert {key for key, _ in REGISTRY} == V1_KEYS
    assert all(version == 1 for _, version in REGISTRY)
    assert {spec.key for spec in REGISTRY.values() if spec.soft_only} == SOFT_ONLY


def test_DOM_05_unknown_template_and_version() -> None:
    with pytest.raises(UnknownTemplate, match="unknown template 'nope'"):
        get_template("nope", 1)
    with pytest.raises(UnknownTemplate, match="max_load has no version 9"):
        get_template("max_load", 9)
    with pytest.raises(InvalidInstance) as caught:
        validate_instance("max_load", 9, {}, hard=True, weight=0)
    assert caught.value.problems[0].loc == ("template_version",)


def test_DOM_05_params_validated_and_normalised() -> None:
    params = validate_instance(
        "max_load", 1, {"period": "day", "max_count": 2}, hard=True, weight=0
    )
    assert params == {"period": "day", "window": None, "max_count": 2, "max_minutes": None}


@pytest.mark.parametrize(
    ("key", "params", "loc"),
    [
        ("max_load", {"period": "fortnight", "max_count": 2}, ("params", "period")),
        ("max_load", {"period": "day"}, ("params",)),
        ("max_load", {"period": "day", "max_count": 2, "extra": 1}, ("params", "extra")),
        ("min_rest", {"minutes": 0}, ("params", "minutes")),
        ("spread", {}, ("params",)),
        ("same_time", {"link_groups": [["only-one"]]}, ("params", "link_groups", 0)),
        ("capacity_fit", {"headcount_from": "activity_attr"}, ("params",)),
        ("preference", {"source": "explicit"}, ("params",)),
    ],
)
def test_DOM_05_bad_params_are_located(
    key: str, params: dict[str, object], loc: tuple[object, ...]
) -> None:
    with pytest.raises(InvalidInstance) as caught:
        validate_instance(key, 1, params, hard=key not in SOFT_ONLY, weight=1)
    assert any(p.loc[: len(loc)] == loc for p in caught.value.problems), caught.value.problems


def test_DOM_05_soft_only_and_weight_rules() -> None:
    with pytest.raises(InvalidInstance, match="can only be soft"):
        validate_instance("balance", 1, {"measure": "count"}, hard=True, weight=0)
    with pytest.raises(InvalidInstance, match="weight"):
        validate_instance("balance", 1, {"measure": "count"}, hard=False, weight=0)
    assert validate_instance("balance", 1, {"measure": "count"}, hard=False, weight=5)


def test_DOM_05_every_template_has_a_valid_example() -> None:
    examples: dict[str, dict[str, object]] = {
        "capacity_fit": {},
        "max_load": {"period": "week", "max_minutes": 1320},
        "min_load": {"period": "week", "min_minutes": 600},
        "min_rest": {"minutes": 660},
        "max_consecutive": {"unit": "days", "max": 5},
        "spread": {"max_per_day": 1},
        "same_time": {"link_groups": [["s1", "s2"]]},
        "precedence": {"pairs": [{"before": "s1", "after": "s2"}]},
        "preference": {"source": "calendar"},
        "minimize_gaps": {"per_minutes": 30},
        "balance": {"measure": "minutes"},
        "fairness": {"activity_filter": {"series_ids": ["s1"]}, "lookback_days": 90},
        "day_distribution": {},
        "stability": {"per_change": 10, "per_resource_change": 5},
    }
    assert examples.keys() == V1_KEYS
    for key, params in examples.items():
        validate_instance(key, 1, params, hard=key not in SOFT_ONLY, weight=1)


def test_DOM_05_constraint_instance_model_uses_the_registry() -> None:
    ok = ConstraintInstance(
        id="c1", template_key="min_rest", version=1, params={"minutes": 660}, hard=True
    )
    assert ok.scope.resource_ids == ()
    with pytest.raises(ValidationError, match="unknown template"):
        ConstraintInstance(id="c2", template_key="nope", version=1, hard=True)
