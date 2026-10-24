import random

from tools.loadtest.moves import move_for

VERSION = {
    "assignments": [
        {
            "activity_id": "a1",
            "start_at": "2026-01-12T09:00:00+03:00",
            "resources": {"who": ["p1"]},
        },
        {
            "activity_id": "a2",
            "start_at": "2026-01-13T11:00:00+03:00",
            "resources": {"who": ["p2"]},
        },
    ]
}


def test_move_keeps_resources_and_takes_another_start() -> None:
    move = move_for(VERSION, random.Random(0))
    assert move is not None
    mine = next(a for a in VERSION["assignments"] if a["activity_id"] == move["activity_id"])
    assert move["resources"] == mine["resources"]
    assert move["start_at"] != mine["start_at"]
    assert set(move) == {"activity_id", "start_at", "resources"}


def test_no_move_without_two_assignments() -> None:
    assert move_for({"assignments": VERSION["assignments"][:1]}, random.Random(0)) is None
