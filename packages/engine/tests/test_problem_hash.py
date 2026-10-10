from cartlyf_engine.domain import Problem, SolveOptions, problem_hash

BASE: dict[str, object] = {
    "horizon_minutes": 1440,
    "day_windows": [{"start": 0, "end": 1440}],
    "week_windows": [{"start": 0, "end": 1440}],
    "resources": [
        {"id": "r1", "type_key": "room", "kind": "space", "capacity": 30, "attrs": {"b": 1, "a": 2}}
    ],
    "activities": [{"id": "a1", "duration": 60, "candidate_starts": [0, 60]}],
}


def test_same_data_same_hash() -> None:
    assert problem_hash(Problem.model_validate(BASE)) == problem_hash(Problem.model_validate(BASE))


def test_hash_ignores_dict_key_order_and_solve_options() -> None:
    reordered = BASE | {
        "resources": [
            {
                "id": "r1",
                "type_key": "room",
                "kind": "space",
                "capacity": 30,
                "attrs": {"a": 2, "b": 1},
            }
        ]
    }
    first = Problem.model_validate(BASE)
    second = Problem.model_validate(reordered).model_copy(
        update={"options": SolveOptions(time_limit_s=5, seed=7, num_workers=1)}
    )
    assert problem_hash(first) == problem_hash(second)


def test_any_data_change_changes_hash() -> None:
    changed = BASE | {"horizon_minutes": 1441}
    assert problem_hash(Problem.model_validate(BASE)) != problem_hash(
        Problem.model_validate(changed)
    )


def test_hash_is_hex_sha256() -> None:
    digest = problem_hash(Problem.model_validate(BASE))
    assert len(digest) == 64 and int(digest, 16) >= 0
