"""The part of a schedule one placement can affect, so rules are checked locally.

Every v1 rule's findings are local to a resource, an activity or a series, so comparing before
and after on the neighbourhood gives the same difference as on the whole schedule. Whole-scope
rules (balance, fairness, day_distribution) widen it to everything in their scope."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from cartlyf_engine.checking import CheckContext
from cartlyf_engine.domain import Assignment, ConstraintInstance, Problem
from cartlyf_engine.templates.registry import UnsupportedTemplate, get_template
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import Checker


@dataclass(frozen=True)
class Scoped:
    instance: ConstraintInstance
    check: Checker
    activities: frozenset[str]
    linked: frozenset[str]  # series ids its params name
    resources: frozenset[str]  # whole-scope rules only


@dataclass(frozen=True)
class Local:
    problem: Problem
    placed: dict[str, Assignment]


class Neighbourhood:
    def __init__(self, problem: Problem, instances: Sequence[ConstraintInstance]) -> None:
        self._problem = problem
        self._rules: list[Scoped] = []
        for instance in instances:
            spec = get_template(instance.template_key, instance.version)
            if spec.check is None:
                raise UnsupportedTemplate(instance.template_key)
            params = spec.params_model.model_validate(instance.params)
            whole = scoped_resources(problem, instance.scope) if spec.whole_scope else []
            self._rules.append(
                Scoped(
                    instance,
                    spec.check,
                    frozenset(a.id for a in scoped_activities(problem, instance.scope)),
                    spec.references(params).series_ids,
                    frozenset(r.id for r in whole),
                )
            )
        self._activity_position = {a.id: i for i, a in enumerate(problem.activities)}
        self._resource_position = {r.id: i for i, r in enumerate(problem.resources)}
        self._series: dict[str, list[str]] = {}
        for activity in problem.activities:
            if activity.series_id is not None:
                self._series.setdefault(activity.series_id, []).append(activity.id)

    def rules_for(self, activity_id: str) -> list[Scoped]:
        return [rule for rule in self._rules if activity_id in rule.activities]

    def around(
        self, ctx: CheckContext, activity_id: str, held: Collection[str], rules: Sequence[Scoped]
    ) -> Local:
        """The activity, its series and the series linked to it, everything the `held`
        resources work, and everything in scope of whole-scope rules; only `rules` apply."""
        series_id = ctx.index.activities[activity_id].series_id
        series = {series_id} if series_id is not None else set[str]()
        for rule in rules:
            if series_id in rule.linked:
                series |= rule.linked
        resources = {r for r in held if r in self._resource_position}
        hood = {activity_id} | {a for s in series for a in self._series.get(s, ())}
        hood |= {a.id for r in resources for a in ctx.work(r)}
        for rule in rules:
            if rule.resources:
                hood |= rule.activities
                resources |= rule.resources
        placed = {a: ctx.placed[a] for a in hood if a in ctx.placed}
        resources |= {r for a in placed for r in ctx.holders(a)}
        problem = self._problem
        activities = sorted(self._activity_position[a] for a in hood)
        kept = sorted(self._resource_position[r] for r in resources)
        sub = problem.model_copy(
            update={
                "activities": tuple(problem.activities[i] for i in activities),
                "resources": tuple(problem.resources[i] for i in kept),
                "constraints": tuple(rule.instance for rule in rules),
            }
        )
        return Local(sub, placed)
