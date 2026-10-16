from typing import Any, get_args

from pydantic import BaseModel

from cartlyf_engine.domain.filters import AttributePredicate
from cartlyf_engine.templates.registry import REGISTRY

Schema = dict[str, Any]


def _leaves(schema: Schema, defs: Schema, path: str) -> list[tuple[str, Schema]]:
    if "$ref" in schema:
        schema = defs[schema["$ref"].split("/")[-1]]
    found = [(path, schema)]
    for key, sub in schema.get("properties", {}).items():
        found += _leaves(sub, defs, f"{path}.{key}")
    if "items" in schema:
        found += _leaves(schema["items"], defs, f"{path}[]")
    for option in schema.get("anyOf", []):
        found += _leaves(option, defs, path)
    return found


def _models(model: type[BaseModel]) -> list[type[BaseModel]]:
    found = [model]
    for field in model.model_fields.values():
        stack: list[object] = [field.annotation]
        while stack:
            tp = stack.pop()
            if isinstance(tp, type) and issubclass(tp, BaseModel):
                if tp is not AttributePredicate and tp not in found:
                    found += _models(tp)
            else:
                stack += get_args(tp)
    return found


def test_every_template_has_a_title_and_description() -> None:
    for spec in REGISTRY.values():
        assert spec.title.strip(), spec.key
        assert spec.description.strip().endswith("."), spec.key


def test_every_params_field_has_an_explicit_title() -> None:
    for spec in REGISTRY.values():
        for model in _models(spec.params_model):
            for name, field in model.model_fields.items():
                assert field.title, f"{spec.key}: {model.__name__}.{name}"


def test_every_id_string_names_what_it_refers_to() -> None:
    # An Id-shaped string without x-ref would render as a bare text box instead of a picker.
    for spec in REGISTRY.values():
        schema = spec.params_model.model_json_schema()
        for path, leaf in _leaves(schema, schema.get("$defs", {}), spec.key):
            if leaf.get("type") == "string" and leaf.get("maxLength") == 100:
                assert leaf.get("x-ref") in {"series", "resource"}, path


def _refs(key: str) -> dict[str, str]:
    schema = REGISTRY[(key, 1)].params_model.model_json_schema()
    return {
        path: leaf["x-ref"]
        for path, leaf in _leaves(schema, schema.get("$defs", {}), key)
        if "x-ref" in leaf
    }


def test_references_are_tagged() -> None:
    assert _refs("precedence") == {
        "precedence.pairs[].before": "series",
        "precedence.pairs[].after": "series",
    }
    assert _refs("preference") == {
        "preference.pairs[].resource_id": "resource",
        "preference.pairs[].series_id": "series",
    }
    assert _refs("same_time") == {"same_time.link_groups[][]": "series"}
    assert _refs("fairness") == {"fairness.activity_filter.series_ids[]": "series"}
    assert _refs("max_consecutive") == {"max_consecutive.activity_filter.series_ids[]": "series"}
    assert _refs("max_load") == {"max_load.window": "window"}
    assert _refs("min_load") == {"min_load.window": "window"}


def test_minute_fields_carry_a_unit() -> None:
    expected = {
        "max_load": {"max_minutes"},
        "min_load": {"min_minutes"},
        "min_rest": {"minutes"},
        "minimize_gaps": {"per_minutes"},
        "precedence": {"min_gap"},
    }
    for key, names in expected.items():
        props = REGISTRY[(key, 1)].params_model.model_json_schema()["properties"]
        assert {n for n, p in props.items() if p.get("x-unit") == "minutes"} == names, key
