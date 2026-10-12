from ortools.sat.python import cp_model

from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.encoding import Encoding
from kit import DAY, act, needs, person, problem


def _encoding() -> Encoding:
    p = problem([person("p")], [act("a1", 60, [0, 120, DAY], needs())])
    return compile_problem(p).encoding


def _range(
    enc: Encoding, var: cp_model.IntVar | int, fix: dict[cp_model.IntVar, int]
) -> tuple[int, int]:
    """Smallest and largest feasible value of `var` with the given literals fixed."""
    assert not isinstance(var, int)
    found: list[int] = []
    for sense in (1, -1):
        model = enc.model.clone()
        for lit, value in fix.items():
            model.add(model.get_int_var_from_proto_index(lit.index) == value)
        target = model.get_int_var_from_proto_index(var.index)
        model.minimize(sense * target)
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        assert solver.solve(model) == cp_model.OPTIMAL
        found.append(solver.value(target))
    return found[0], found[1]


def test_bucket_is_shared_and_collapses_trivial_sets() -> None:
    enc = _encoding()
    assert enc.bucket("a1", []) == 0
    assert enc.bucket("a1", [0, 120, DAY]) == 1
    assert enc.bucket("a1", [DAY]) is enc.starts["a1"][DAY]
    shared = enc.bucket("a1", [0, 120])
    assert enc.bucket("a1", [120, 0]) is shared


def test_conj_directions() -> None:
    enc = _encoding()
    a, b = enc.model.new_bool_var("a"), enc.model.new_bool_var("b")
    over, under, exact = enc.conj(a, b, "over"), enc.conj(a, b, "under"), enc.conj(a, b, "exact")
    assert enc.conj(a, 0, "over") == 0
    assert enc.conj(a, 1, "under") is a
    assert _range(enc, over, {a: 1, b: 1}) == (1, 1)
    assert _range(enc, over, {a: 1, b: 0}) == (0, 1)
    assert _range(enc, under, {a: 1, b: 1}) == (0, 1)
    assert _range(enc, under, {a: 0, b: 1}) == (0, 0)
    assert _range(enc, exact, {a: 1, b: 0}) == (0, 0)
    assert _range(enc, exact, {a: 1, b: 1}) == (1, 1)


def test_breach_is_forced_only_when_the_condition_fails() -> None:
    enc = _encoding()
    x = enc.model.new_int_var(0, 10, "x")
    v = enc.breach(x <= 5)
    flag = enc.model.new_bool_var("flag")
    enc.when(x == 7, flag)
    enc.when(x == 3, ~flag)
    assert _range(enc, v, {flag: 1}) == (1, 1)
    assert _range(enc, v, {flag: 0}) == (0, 1)
