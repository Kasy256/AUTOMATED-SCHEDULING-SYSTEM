from pydantic import NonNegativeInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    per_change: NonNegativeInt
    per_resource_change: NonNegativeInt


SPEC = TemplateSpec("stability", 1, Params, soft_only=True)
