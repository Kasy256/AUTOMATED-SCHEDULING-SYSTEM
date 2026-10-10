from pydantic import PositiveInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    minutes: PositiveInt


SPEC = TemplateSpec("min_rest", 1, Params)
