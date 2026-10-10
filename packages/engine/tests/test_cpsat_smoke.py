from ortools.sat.python import cp_model


def test_cpsat_solves_two_variable_model() -> None:
    model = cp_model.CpModel()
    x = model.new_int_var(0, 10, "x")
    y = model.new_int_var(0, 10, "y")
    model.add(x + y == 10)
    model.add(x - y == 2)

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)

    assert status == cp_model.OPTIMAL
    assert (solver.value(x), solver.value(y)) == (6, 4)
