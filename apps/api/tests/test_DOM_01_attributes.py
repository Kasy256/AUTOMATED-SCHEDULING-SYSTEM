from collections.abc import Mapping

import pytest
from pydantic import ValidationError

from cartlyf_api.resources.attribute_schema import AttributeSchema, coerce_cell, validate_attributes

SCHEMA = AttributeSchema.model_validate(
    {
        "version": 1,
        "attributes": [
            {
                "key": "room_type",
                "type": "enum",
                "enum_values": ["lecture", "lab"],
                "required": True,
            },
            {"key": "floor", "type": "integer"},
            {"key": "area", "type": "number"},
            {"key": "accessible", "type": "boolean"},
            {"key": "label", "type": "string"},
            {"key": "features", "type": "tags"},
        ],
    }
)


def errors(values: Mapping[str, object]) -> dict[str | int, str]:
    return {e["loc"][-1]: e["msg"] for e in validate_attributes(SCHEMA, values, ("attributes",))}


def test_DOM_01_valid_values_pass() -> None:
    values = {
        "room_type": "lab",
        "floor": 2,
        "area": 40.5,
        "accessible": False,
        "label": "Chem",
        "features": ["fume_hood", "sink"],
    }
    assert errors(values) == {}


@pytest.mark.parametrize(
    ("values", "key", "message"),
    [
        ({}, "room_type", "Field required"),
        ({"room_type": "kitchen"}, "room_type", "must be one of: lecture, lab"),
        ({"room_type": "lab", "floor": 2.5}, "floor", "must be a whole number"),
        ({"room_type": "lab", "floor": True}, "floor", "must be a whole number"),
        ({"room_type": "lab", "area": "big"}, "area", "must be a number"),
        ({"room_type": "lab", "accessible": 1}, "accessible", "must be true or false"),
        ({"room_type": "lab", "label": 5}, "label", "must be text"),
        ({"room_type": "lab", "features": ["a", "a"]}, "features", "distinct"),
        ({"room_type": "lab", "colour": "red"}, "colour", "Unknown attribute"),
    ],
)
def test_DOM_01_each_type_rejects_bad_values(
    values: dict[str, object], key: str, message: str
) -> None:
    assert message in errors(values)[key]


def test_DOM_01_schema_itself_is_validated() -> None:
    with pytest.raises(ValidationError, match="enum_values"):
        AttributeSchema.model_validate({"attributes": [{"key": "k", "type": "enum"}]})
    with pytest.raises(ValidationError, match="enum_values"):
        AttributeSchema.model_validate(
            {"attributes": [{"key": "k", "type": "string", "enum_values": ["a"]}]}
        )
    with pytest.raises(ValidationError, match="unique"):
        AttributeSchema.model_validate(
            {"attributes": [{"key": "k", "type": "string"}, {"key": "k", "type": "integer"}]}
        )
    with pytest.raises(ValidationError):
        AttributeSchema.model_validate({"attributes": [{"key": "Bad Key", "type": "string"}]})


@pytest.mark.parametrize(
    ("key", "cell", "expected"),
    [
        ("floor", "3", 3),
        ("area", "2.5", 2.5),
        ("accessible", "Yes", True),
        ("accessible", "0", False),
        ("features", "a; b ;", ["a", "b"]),
        ("label", " Chem ", "Chem"),
        ("floor", "three", "three"),
    ],
)
def test_coerce_csv_cells(key: str, cell: str, expected: object) -> None:
    definition = next(d for d in SCHEMA.attributes if d.key == key)
    assert coerce_cell(definition, cell) == expected


@pytest.mark.parametrize(("key", "cell"), [("floor", "--5"), ("floor", "²"), ("area", "1e999")])
def test_coerce_never_raises_and_rejects_non_finite(key: str, cell: str) -> None:
    definition = next(d for d in SCHEMA.attributes if d.key == key)
    assert coerce_cell(definition, cell) == cell
    assert errors({"room_type": "lab", key: coerce_cell(definition, cell)})[key]
