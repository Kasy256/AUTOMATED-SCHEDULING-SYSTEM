from collections.abc import Mapping
from typing import Literal, Self

from pydantic import StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from cartlyf_engine.domain.base import Frozen, Id, Key, Tag

AttrScalar = StrictStr | StrictInt | StrictFloat | StrictBool
AttrValue = AttrScalar | tuple[StrictStr, ...]
PredicateOp = Literal["eq", "ne", "in", "gte", "lte", "contains"]


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


class AttributePredicate(Frozen):
    attr: Key
    op: PredicateOp
    value: AttrScalar | tuple[AttrScalar, ...]

    @model_validator(mode="after")
    def _value_fits_op(self) -> Self:
        is_list = isinstance(self.value, tuple)
        if (self.op == "in") != is_list:
            raise ValueError(
                f"'{self.op}' needs {'a list' if self.op == 'in' else 'a single'} value"
            )
        if self.op in ("gte", "lte") and not _is_number(self.value):
            raise ValueError(f"'{self.op}' needs a number")
        if self.op == "contains" and not isinstance(self.value, str):
            raise ValueError("'contains' needs a string")
        return self


def _equal(actual: AttrValue, expected: AttrScalar) -> bool:
    # bool is an int in Python; True must not equal 1 here.
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def predicate_holds(attrs: Mapping[str, AttrValue], predicate: AttributePredicate) -> bool:
    """A missing attribute satisfies no predicate, not even `ne`."""
    if predicate.attr not in attrs:
        return False
    actual, expected = attrs[predicate.attr], predicate.value
    match predicate.op:
        case "eq":
            return not isinstance(expected, tuple) and _equal(actual, expected)
        case "ne":
            return not isinstance(expected, tuple) and not _equal(actual, expected)
        case "in":
            return isinstance(expected, tuple) and any(_equal(actual, v) for v in expected)
        case "gte" | "lte":
            if not (isinstance(actual, int | float) and isinstance(expected, int | float)):
                return False
            if isinstance(actual, bool) or isinstance(expected, bool):
                return False
            return actual >= expected if predicate.op == "gte" else actual <= expected
        case "contains":
            return isinstance(actual, tuple) and expected in actual


class ResourceFilter(Frozen):
    """Matches resources of a type (optional) having all `tags` and satisfying all `attrs`."""

    type_key: Key | None = None
    tags: tuple[Tag, ...] = ()
    attrs: tuple[AttributePredicate, ...] = ()


class ActivityFilter(Frozen):
    series_ids: tuple[Id, ...] = ()
    attrs: tuple[AttributePredicate, ...] = ()
