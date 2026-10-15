"""First-fit construction of a schedule so CP-SAT starts from a solution instead of searching for
one. Hard rules are judged by the independent checker; this module holds no rule logic."""

from collections.abc import Callable, Iterator, Mapping
from itertools import islice
from math import prod
from typing import NamedTuple

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, Assignment, ConstraintInstance, Problem
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.registry import UnsupportedTemplate, get_template
from cartlyf_engine.templates.scope import scoped_activities
from cartlyf_engine.templates.spec import Checker

_OPTIONS_PER_START = 8


def construct(
    problem: Problem,
    keep_going: Callable[[], bool] = lambda: True,
    max_evaluations: int | None = None,
    prefer: Mapping[str, Assignment] | None = None,
) -> tuple[Assignment, ...]:
    """Place pinned activities first, then the most constrained, each at the first option that
    keeps the core rules and adds no hard-rule finding. With `prefer` (a repair baseline), an
    activity tries its preferred start and resources first. Unplaceable activities are left out."""
    index = ProblemIndex(problem)
    ctx = CheckContext(problem, index, {})
    timeline = _Timeline(problem)
    judge = _Judge(problem)
    position = {a.id: i for i, a in enumerate(problem.activities)}
    evaluations = 0
    for activity in sorted(problem.activities, key=lambda a: (_rank(index, a), position[a.id])):
        if not keep_going():
            break
        placed = False
        for forced, fills in _starts(index, timeline, activity, (prefer or {}).get(activity.id)):
            for option in (forced, *islice(fills, _OPTIONS_PER_START)):
                if max_evaluations is not None and evaluations >= max_evaluations:
                    return _in_order(ctx, position)
                evaluations += 1
                if not judge.accepts(ctx, option):
                    if option is forced:
                        # Adding resources never removes a hard finding, so the start is lost.
                        break
                    continue
                if option is not forced or _complete(activity, option):
                    ctx.place(option)
                    timeline.book(index, activity, option)
                    placed = True
                    break
            if placed:
                break
    return _in_order(ctx, position)


def _in_order(ctx: CheckContext, position: dict[str, int]) -> tuple[Assignment, ...]:
    return tuple(sorted(ctx.placed.values(), key=lambda a: position[a.activity_id]))


def _rank(index: ProblemIndex, activity: Activity) -> tuple[int, int]:
    pinned = 0 if activity.pinned is not None else 1
    options = len(activity.candidate_starts) * prod(
        max(1, len(index.eligible(activity.id, r.role))) for r in activity.requirements
    )
    return pinned, options


class _Pool(NamedTuple):
    role: str
    forced: tuple[str, ...]
    free: list[str]
    extra: int
    hard: bool


class _Timeline:
    """Core rules: concurrency and unavailable windows per resource."""

    def __init__(self, problem: Problem) -> None:
        self._busy: dict[str, list[tuple[int, int]]] = {r.id: [] for r in problem.resources}
        self._blocked = {r.id: r.unavailable for r in problem.resources}
        self._limit = {r.id: r.concurrency for r in problem.resources}

    def free(self, resource_id: str, start: int, end: int) -> bool:
        if any(w.start < end and start < w.end for w in self._blocked[resource_id]):
            return False
        overlapping = [(s, e) for s, e in self._busy[resource_id] if s < end and start < e]
        # Load inside [start, end) peaks at `start` or at the start of an overlapping booking.
        points = {start} | {s for s, _ in overlapping if s > start}
        limit = self._limit[resource_id]
        return all(sum(1 for s, e in overlapping if s <= t < e) < limit for t in points)

    def book(self, index: ProblemIndex, activity: Activity, option: Assignment) -> None:
        for ids in option.resources.values():
            for resource_id in ids:
                if resource_id in index.resources:
                    self._busy[resource_id].append((option.start, option.start + activity.duration))


class _Judge:
    """Accepts a placement only if no hard instance gains a finding. Rules are checked on the
    placement's neighbourhood (activities sharing a resource or series with it) because every v1
    hard rule's findings are local to a resource, an activity or a series; comparing before and
    after on the same neighbourhood gives the same difference as on the whole schedule."""

    def __init__(self, problem: Problem) -> None:
        self._problem = problem
        self._rules: list[tuple[ConstraintInstance, Checker, frozenset[str], frozenset[str]]] = []
        for instance in problem.constraints:
            if not instance.hard:
                continue
            spec = get_template(instance.template_key, instance.version)
            if spec.check is None:
                raise UnsupportedTemplate(instance.template_key)
            in_scope = frozenset(a.id for a in scoped_activities(problem, instance.scope))
            linked = spec.references(spec.params_model.model_validate(instance.params)).series_ids
            self._rules.append((instance, spec.check, in_scope, linked))
        self._position = {a.id: i for i, a in enumerate(problem.activities)}
        self._resources = {r.id: r for r in problem.resources}
        self._series: dict[str, list[str]] = {}
        for activity in problem.activities:
            if activity.series_id is not None:
                self._series.setdefault(activity.series_id, []).append(activity.id)

    def accepts(self, ctx: CheckContext, option: Assignment) -> bool:
        activity_id = option.activity_id
        rules = [rule for rule in self._rules if activity_id in rule[2]]
        if not rules:
            return True
        series_id = ctx.index.activities[activity_id].series_id
        series = {series_id} if series_id is not None else set[str]()
        for _, _, _, linked in rules:
            if series_id in linked:
                series |= linked
        held = {r for ids in option.resources.values() for r in ids if r in ctx.index.resources}
        hood = {activity_id} | {a for s in series for a in self._series.get(s, ())}
        hood |= {a.id for r in held for a in ctx.work(r)}
        placed = {a: ctx.placed[a] for a in hood if a in ctx.placed}
        resources = held | {r for a in placed for r in ctx.holders(a)}
        sub = self._problem.model_copy(
            update={
                "activities": tuple(
                    self._problem.activities[i] for i in sorted(self._position[a] for a in hood)
                ),
                "resources": tuple(self._resources[r] for r in sorted(resources)),
                "constraints": tuple(instance for instance, *_ in rules),
            }
        )
        # Lookups by id only, so the full problem's index serves the neighbourhood too.
        local = CheckContext(sub, ctx.index, placed)
        before = [_count(check(local, instance)) for instance, check, *_ in rules]
        local.place(option)
        after = [_count(check(local, instance)) for instance, check, *_ in rules]
        return all(a <= b for a, b in zip(after, before, strict=True))


def _count(findings: list[Finding]) -> int:
    return sum(1 for f in findings if f.amount > 0)


def _starts(
    index: ProblemIndex, timeline: _Timeline, activity: Activity, preferred: Assignment | None
) -> Iterator[tuple[Assignment, Iterator[Assignment]]]:
    """Per feasible start: the option with only fixed/pinned resources, then full options.
    A preferred placement's start comes first and its resources lead each role's pool."""
    pin = activity.pinned
    pinned = pin.resources if pin is not None else {}
    if pin is not None and pin.start is not None:
        starts = [pin.start]
    else:
        starts = list(activity.candidate_starts)
    if preferred is not None and preferred.start in starts:
        starts.remove(preferred.start)
        starts.insert(0, preferred.start)
    for start in starts:
        end = start + activity.duration
        pools: list[_Pool] = []
        for req in activity.requirements:
            eligible = index.eligible(activity.id, req.role)
            forced = tuple(dict.fromkeys((*req.fixed_resource_ids, *pinned.get(req.role, ()))))
            if any(r not in eligible or not timeline.free(r, start, end) for r in forced):
                break
            free = [r for r in eligible if r not in forced and timeline.free(r, start, end)]
            if preferred is not None:
                liked = set(preferred.resources.get(req.role, ()))
                free.sort(key=lambda r: r not in liked)
            need = max(req.count_min - len(forced), 0)
            if req.hard and len(free) < need:
                break
            pools.append(_Pool(req.role, forced, free, min(need, len(free)), req.hard))
        else:
            bare = Assignment(
                activity_id=activity.id,
                start=start,
                resources={pool.role: pool.forced for pool in pools},
            )
            yield bare, _fills(activity.id, start, pools)


def _complete(activity: Activity, option: Assignment) -> bool:
    """The forced-only option is itself a full placement when no role needs more resources."""
    return all(len(option.resources.get(r.role, ())) >= r.count_min for r in activity.requirements)


def _fills(activity_id: str, start: int, pools: list[_Pool]) -> Iterator[Assignment]:
    """Options that rotate every role's choice at once, never reusing a resource another role
    of the same option already took, so a few tries move past busy resources in every role."""
    forced = [r for pool in pools for r in pool.forced]
    if len(forced) != len(set(forced)):
        return
    widest = max((len(pool.free) for pool in pools), default=0)
    seen: set[tuple[tuple[str, tuple[str, ...]], ...]] = set()
    for i in range(max(1, widest)):
        taken = set(forced)
        resources: dict[str, tuple[str, ...]] = {}
        for pool in pools:
            offset = i % len(pool.free) if pool.free else 0
            rotated = pool.free[offset:] + pool.free[:offset]
            extra = tuple(r for r in rotated if r not in taken)[: pool.extra]
            if pool.hard and len(extra) < pool.extra:
                break
            taken |= set(extra)
            resources[pool.role] = pool.forced + extra
        else:
            key = tuple(sorted(resources.items()))
            if key not in seen:
                seen.add(key)
                yield Assignment(activity_id=activity_id, start=start, resources=resources)
