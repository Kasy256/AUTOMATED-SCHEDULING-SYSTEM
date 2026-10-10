from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    version: int
    params_model: type[BaseModel]
    # Objective-only rules (preferences, balance, stability…) cannot be hard.
    soft_only: bool = False
