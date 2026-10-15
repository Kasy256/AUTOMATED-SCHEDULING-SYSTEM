import random
import time
from pathlib import Path

from cartlyf_engine.construct import construct
from cartlyf_engine.domain import Problem
from cartlyf_engine.moves import MoveChecker

FIXTURE = Path(__file__).parent / "fixtures/isbat/v1/term1_problem.json"


def test_EXP_05_move_checks_are_fast_on_isbat() -> None:
    p = Problem.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    plan = construct(p)
    checker = MoveChecker(p, plan)
    rng = random.Random(0)
    times: list[float] = []
    for _ in range(200):
        placed = rng.choice(plan)
        starts = checker.index.activities[placed.activity_id].candidate_starts
        move = placed.model_copy(update={"start": rng.choice(starts)})
        began = time.perf_counter()
        checker.check(move)
        times.append(time.perf_counter() - began)
    times.sort()
    # The API budget is 200 ms p95 (EXP-05); the engine's share must stay within half of it.
    assert times[int(0.95 * len(times))] < 0.1
