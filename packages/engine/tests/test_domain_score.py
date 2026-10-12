import pytest
from pydantic import ValidationError

from cartlyf_engine.domain import REQUIREMENTS_TERM, Score, SolveStats, Violation
from kit import act, needs, person, problem, rule


def test_score_lists_violations() -> None:
    v = Violation(constraint_id="c1", message="too many", activity_ids=("a1",))
    score = Score(hard_violations=1, soft_total=0, violations=(v,))
    assert score.violations[0].resource_ids == ()
    assert Score(hard_violations=0, soft_total=0).violations == ()


def test_stats_carry_the_solver_objective() -> None:
    assert SolveStats(wall_time_s=0.1).objective is None
    assert SolveStats(wall_time_s=0.1, objective=7).objective == 7


def test_core_ids_are_reserved_names() -> None:
    assert REQUIREMENTS_TERM == "core:requirements"


def test_problem_rejects_a_rule_naming_an_unknown_window() -> None:
    with pytest.raises(ValidationError, match="unknown window 'evening'"):
        problem(
            [person("p")],
            [act("a1", 60, [0], needs())],
            [rule("c1", "max_load", period="day", window="evening", max_count=1)],
        )
