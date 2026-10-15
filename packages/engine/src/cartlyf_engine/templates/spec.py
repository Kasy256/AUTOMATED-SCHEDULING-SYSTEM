from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from cartlyf_engine.checking import CheckContext, Finding
    from cartlyf_engine.domain.constraints import ConstraintInstance
    from cartlyf_engine.encoding import Rule

Encoder = Callable[["Rule", "ConstraintInstance"], None]
Checker = Callable[["CheckContext", "ConstraintInstance"], "list[Finding]"]
Explainer = Callable[["ConstraintInstance"], str]


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
    # Findings compare resources across the whole scope (balance, fairness), so a local check
    # must see everything in scope.
    whole_scope: bool = False
    references: Callable[[BaseModel], References] = field(default=_no_references)
    encode: Encoder | None = None
    check: Checker | None = None
    explain: Explainer | None = None
