from pydantic import PositiveInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    per_minutes: PositiveInt


SPEC = TemplateSpec("minimize_gaps", 1, Params, soft_only=True)
