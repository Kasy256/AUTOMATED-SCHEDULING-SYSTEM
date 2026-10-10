from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    pass


SPEC = TemplateSpec("day_distribution", 1, Params, soft_only=True)
