"""solve(): compile, run CP-SAT with progress and cancel, score the result with the checker."""

import threading
from collections.abc import Callable
from typing import Literal

from ortools.sat.python import cp_model

from cartlyf_engine.checker import check
from cartlyf_engine.compiler import Compiled, compile_problem
from cartlyf_engine.construct import construct
from cartlyf_engine.domain import (
    Assignment,
    Frozen,
    Problem,
    Score,
    Solution,
    SolveOptions,
    SolveStats,
    SolveStatus,
)
from cartlyf_engine.lns import Incumbent, decode, improve


class Progress(Frozen):
    kind: Literal["solution", "bound", "log", "constructed"]
    objective: int | None = None
    best_bound: float | None = None
    wall_time_s: float | None = None
    solutions: int = 0
    message: str = ""


ProgressFn = Callable[[Progress], None]


class CancelToken:
    """Call cancel() from any thread; the running solve stops with its best-so-far."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._stop: Callable[[], None] | None = None

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            stop = self._stop
        if stop is not None:
            stop()

    def attach(self, stop: Callable[[], None] | None) -> None:
        with self._lock:
            self._stop = stop


class _Callback(cp_model.CpSolverSolutionCallback):
    def __init__(self, on_progress: ProgressFn | None, cancel: CancelToken | None) -> None:
        super().__init__()
        self._on_progress = on_progress
        self._cancel = cancel
        self.solutions = 0

    def on_solution_callback(self) -> None:
        self.solutions += 1
        if self._on_progress is not None:
            self._on_progress(
                Progress(
                    kind="solution",
                    objective=round(self.objective_value),
                    best_bound=self.best_objective_bound,
                    wall_time_s=self.wall_time,
                    solutions=self.solutions,
                )
            )
        # stop_search() before the search starts is lost; re-check on every solution.
        if self._cancel is not None and self._cancel.cancelled:
            self.stop_search()


_STATUS = {
    cp_model.OPTIMAL: SolveStatus.OPTIMAL,
    cp_model.FEASIBLE: SolveStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
    cp_model.UNKNOWN: SolveStatus.UNKNOWN,
}
_NO_SCORE = Score(hard_violations=0, soft_total=0)
_FIRST_SOLVE_SHARE = 0.1
# Enough first-fit evaluations for a few options per activity; ENG-08 sizes it (ADR 0010).
_EVALUATIONS_PER_ACTIVITY = 50


def solve(
    problem: Problem,
    options: SolveOptions | None = None,
    on_progress: ProgressFn | None = None,
    cancel: CancelToken | None = None,
) -> Solution:
    """Infeasibility is a result (INFEASIBLE + conflicting hard instance ids), never an
    exception. The score always comes from the independent checker."""
    options = options or problem.options
    compiled = compile_problem(problem)
    plan = construct(
        problem,
        keep_going=lambda: cancel is None or not cancel.cancelled,
        max_evaluations=_EVALUATIONS_PER_ACTIVITY * max(1, len(problem.activities)),
        prefer={b.activity_id: b for b in problem.baseline or ()},
    )
    built = check(problem, plan)
    verified = len(plan) == len(problem.activities) and built.hard_violations == 0
    if verified and on_progress is not None:
        on_progress(Progress(kind="constructed", objective=built.soft_total))
    _hint(compiled, plan)

    def constructed(wall_time_s: float) -> Solution:
        return Solution(
            status=SolveStatus.FEASIBLE,
            assignments=plan,
            score=built,
            stats=SolveStats(wall_time_s=wall_time_s, objective=built.soft_total),
        )

    solver = cp_model.CpSolver()
    # A verified start leaves part of the budget to LNS, which improves where one search stalls.
    first_s = options.time_limit_s * (_FIRST_SOLVE_SHARE if verified else 1.0)
    solver.parameters.max_time_in_seconds = first_s
    solver.parameters.random_seed = options.seed
    solver.parameters.num_workers = options.num_workers
    if on_progress is not None:
        solver.parameters.log_search_progress = True
        solver.parameters.log_to_stdout = False
        solver.log_callback = lambda line: on_progress(Progress(kind="log", message=line))
        solver.best_bound_callback = lambda bound: on_progress(
            Progress(kind="bound", best_bound=bound)
        )
    if cancel is not None:
        cancel.attach(solver.stop_search)
        if cancel.cancelled:
            cancel.attach(None)
            if verified:
                return constructed(0)
            return Solution(
                status=SolveStatus.UNKNOWN, score=_NO_SCORE, stats=SolveStats(wall_time_s=0)
            )
    try:
        code = solver.solve(compiled.model, _Callback(on_progress, cancel))
    finally:
        if cancel is not None:
            cancel.attach(None)
    status = _STATUS.get(code)
    if status is None:
        raise RuntimeError(f"CP-SAT rejected the model: {solver.status_name(code)}")

    if verified and status is SolveStatus.INFEASIBLE:
        raise RuntimeError("CP-SAT reports INFEASIBLE for a checker-verified schedule")
    found = status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)
    start = Incumbent(plan, built, built.soft_total) if verified else None
    proven = False
    if found:
        assignments = decode(problem, compiled, solver)
        score = check(problem, assignments)
        better = score.soft_total <= built.soft_total or status is SolveStatus.OPTIMAL
        # A checker-verified construction always beats a search result the checker rejects.
        if not verified or (score.hard_violations == 0 and better):
            start = Incumbent(assignments, score, round(solver.objective_value))
            proven = status is SolveStatus.OPTIMAL
    if start is None:
        conflicts = _conflicts(problem, options) if status is SolveStatus.INFEASIBLE else ()
        return Solution(
            status=status,
            score=_NO_SCORE,
            conflicts=conflicts,
            stats=SolveStats(wall_time_s=solver.wall_time),
        )
    wall = solver.wall_time
    if not proven and start.score.hard_violations == 0:
        start, lns_wall = _improve(problem, compiled, start, options, wall, on_progress, cancel)
        wall += lns_wall
    stats = SolveStats(wall_time_s=wall, objective=start.objective)
    if found:
        bound = solver.best_objective_bound
        objective = start.objective or 0
        stats = stats.model_copy(
            update={"objective_bound": bound, "gap": (objective - bound) / max(1, abs(objective))}
        )
    return Solution(
        status=SolveStatus.OPTIMAL if proven else SolveStatus.FEASIBLE,
        assignments=start.assignments,
        score=start.score,
        stats=stats,
    )


def _improve(
    problem: Problem,
    compiled: Compiled,
    start: Incumbent,
    options: SolveOptions,
    spent_s: float,
    on_progress: ProgressFn | None,
    cancel: CancelToken | None,
) -> tuple[Incumbent, float]:
    def improved(incumbent: Incumbent, wall_s: float) -> None:
        if on_progress is not None:
            on_progress(
                Progress(
                    kind="solution", objective=incumbent.objective, wall_time_s=spent_s + wall_s
                )
            )

    return improve(
        problem,
        compiled,
        start,
        options,
        wall_budget_s=options.time_limit_s - spent_s,
        keep_going=lambda: cancel is None or not cancel.cancelled,
        attach=cancel.attach if cancel is not None else lambda _: None,
        on_improved=improved,
    )


def _hint(compiled: Compiled, plan: tuple[Assignment, ...]) -> None:
    model, enc = compiled.model, compiled.encoding
    for placed in plan:
        activity_id = placed.activity_id
        for start, lit in enc.starts[activity_id].items():
            model.add_hint(lit, int(start == placed.start))
        model.add_hint(enc.start[activity_id], placed.start)
        chosen: set[str] = set()
        for role, picks in compiled.picks[activity_id].items():
            for resource_id, lit in picks.items():
                on = resource_id in placed.resources.get(role, ())
                model.add_hint(lit, int(on))
                if on:
                    chosen.add(resource_id)
        for resource_id in enc.index.candidates(activity_id):
            use = enc.uses.get((activity_id, resource_id))
            if use is not None:
                model.add_hint(use, int(resource_id in chosen))


def _conflicts(problem: Problem, options: SolveOptions) -> tuple[str, ...]:
    """Hard instances that together make the problem infeasible, from an assumption solve."""
    compiled = compile_problem(problem, assumptions=True)
    if not compiled.hard:
        return ()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = options.time_limit_s
    solver.parameters.random_seed = options.seed
    solver.parameters.num_workers = 1
    if solver.solve(compiled.model) != cp_model.INFEASIBLE:
        return ()
    found = solver.sufficient_assumptions_for_infeasibility()
    return tuple(sorted(compiled.hard[i] for i in found if i in compiled.hard))
