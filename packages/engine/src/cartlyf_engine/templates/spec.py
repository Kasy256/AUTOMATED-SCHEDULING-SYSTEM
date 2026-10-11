from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel


@dataclass(frozen=True)
class References:
    """Ids that a template's params name; the API resolves them on write and guards deletes."""

    series_ids: frozenset[str] = frozenset()
    resource_ids: frozenset[str] = frozenset()


def _no_references(_: BaseModel) -> References:
    return References()


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    version: int
    params_model: type[BaseModel]
    # Objective-only rules (preferences, balance, stability…) cannot be hard.
    soft_only: bool = False
    references: Callable[[BaseModel], References] = field(default=_no_references)
