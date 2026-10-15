from datetime import UTC, datetime
from uuid import UUID, uuid4

from cartlyf_api.versions.diff import Placed, diff

T0 = datetime(2026, 1, 5, 8, tzinfo=UTC)
T1 = datetime(2026, 1, 5, 10, tzinfo=UTC)


def placed(start: datetime, *resources: UUID) -> Placed:
    return start, {"person": frozenset(resources)}


def test_diff_classifies_added_removed_moved_reassigned() -> None:
    r1, r2 = uuid4(), uuid4()
    same, gone, new, moved, reassigned, both = (uuid4() for _ in range(6))
    before = {
        same: placed(T0, r1),
        gone: placed(T0, r1),
        moved: placed(T0, r1),
        reassigned: placed(T0, r1),
        both: placed(T0, r1),
    }
    after = {
        same: placed(T0, r1),
        new: placed(T0, r2),
        moved: placed(T1, r1),
        reassigned: placed(T0, r2),
        both: placed(T1, r2),
    }
    result = diff(before, after)
    assert result.added == [new]
    assert result.removed == [gone]
    assert sorted(result.moved) == sorted([moved, both])
    assert result.reassigned == [reassigned]


def test_diff_identical_is_empty() -> None:
    a = uuid4()
    result = diff({a: placed(T0)}, {a: placed(T0)})
    assert not (result.added or result.removed or result.moved or result.reassigned)
