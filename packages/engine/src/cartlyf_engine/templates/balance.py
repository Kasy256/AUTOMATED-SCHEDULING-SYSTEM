from typing import Literal

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    measure: Literal["count", "minutes"]


SPEC = TemplateSpec("balance", 1, Params, soft_only=True)
