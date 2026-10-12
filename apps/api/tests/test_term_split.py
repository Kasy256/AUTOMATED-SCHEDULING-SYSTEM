from cartlyf_api.imports.schemas import TermSplit
from cartlyf_api.imports.term_split import MergeColumns, split_rows, term_number

SPLIT = TermSplit(
    term="Term 1",
    term_column="term",
    unit_column="unit",
    group_column="group",
    merge_column="subject",
    pair_column="pair",
    prefer={"room_type": ["Lab", "Theory"]},
)
MERGE = MergeColumns(
    lists={"group", "subject"},
    maxima={"weekly_minutes"},
    attrs={"room_type": "room_type"},
    agree={"subject"},
)


def row(group: str, unit: str, subject: str, term: str, **extra: str) -> dict[str, str]:
    values = {
        "group": group,
        "unit": unit,
        "subject": subject,
        "term": term,
        "pair": "",
        "room_type": "Theory",
        "weekly_minutes": "240",
    }
    return values | extra


def lines(*records: dict[str, str]) -> list[tuple[int, dict[str, str]]]:
    return [(i + 2, r) for i, r in enumerate(records)]


def test_term_number_parses_legacy_spellings() -> None:
    assert [term_number(t) for t in ["Term 1", "term1", " 2 ", "TERM 2", "T1", "", "first"]] == [
        1,
        1,
        2,
        2,
        None,
        None,
        None,
    ]


def test_rows_outside_term_are_skipped_and_counted() -> None:
    result = split_rows(
        lines(row("G1", "U1", "S1", "Term 1"), row("G1", "U2", "S2", "Term 2")), SPLIT, MERGE
    )
    assert result.errors == []
    assert [r["subject"] for _, r in result.rows] == ["S1"]
    assert result.skipped == 1


def test_pair_majority_keeps_theory_and_practical_together() -> None:
    result = split_rows(
        lines(
            row("G1", "T", "S", "Term 1", pair="P"),
            row("G1", "P1", "S", "Term 2", pair="P", room_type="Lab"),
            row("G1", "P2", "S", "Term 1", pair="P"),
        ),
        SPLIT,
        MERGE,
    )
    assert result.skipped == 0
    [(line, merged)] = result.rows
    assert line == 2
    assert merged["room_type"] == "Lab"


def test_canonical_alignment_follows_pair_term() -> None:
    # BIT's theory+practical pair is Term 1; BCS's lone unit of the same subject says Term 2.
    result = split_rows(
        lines(
            row("BIT", "BIT1", "S", "Term 1", pair="P"),
            row("BIT", "BIT2", "S", "Term 1", pair="P"),
            row("BCS", "BCS1", "S", "Term 2"),
        ),
        SPLIT,
        MERGE,
    )
    [(_, merged)] = result.rows
    assert merged["group"] == "BIT;BCS"
    assert result.skipped == 0


def test_alignment_majority_vote_without_pairs() -> None:
    result = split_rows(
        lines(
            row("A", "A1", "S", "Term 2"),
            row("B", "B1", "S", "Term 2"),
            row("C", "C1", "S", "Term 1"),
        ),
        SPLIT,
        MERGE,
    )
    assert result.rows == [] and result.skipped == 3


def test_a_single_unit_shared_by_groups_keeps_its_own_term() -> None:
    # Alignment only applies across *different* units; one unit keeps each row's own term.
    result = split_rows(
        lines(row("A", "U", "S", "Term 1"), row("B", "U", "S", "Term 2")), SPLIT, MERGE
    )
    [(_, merged)] = result.rows
    assert merged["group"] == "A" and result.skipped == 1


def test_merge_unions_groups_and_takes_max_minutes() -> None:
    result = split_rows(
        lines(
            row("A", "U1", "S", "Term 1", weekly_minutes="120"),
            row("B", "U2", "S", "Term 1", weekly_minutes="240"),
            row("A", "U3", "S", "Term 1", weekly_minutes="60"),
        ),
        SPLIT,
        MERGE,
    )
    [(_, merged)] = result.rows
    assert merged["group"] == "A;B"
    assert merged["weekly_minutes"] == "240"


def test_merge_conflict_without_preference_is_row_error() -> None:
    split = SPLIT.model_copy(update={"prefer": {}})
    result = split_rows(
        lines(row("A", "U1", "S", "Term 1"), row("B", "U2", "S", "Term 1", room_type="Lab")),
        split,
        MERGE,
    )
    assert result.rows == []
    [error] = result.errors
    assert (error.row, error.column) == (2, "room_type")
    assert "Lab" in error.message and "Theory" in error.message


def test_unreadable_minutes_are_left_for_row_validation() -> None:
    # The demand row check reports the bad cell, alongside every other row error.
    result = split_rows(
        lines(row("A", "U1", "S", "Term 1"), row("B", "U2", "S", "Term 1", weekly_minutes="x")),
        SPLIT,
        MERGE,
    )
    [(_, merged)] = result.rows
    assert result.errors == [] and merged["weekly_minutes"] == "x"


def test_missing_term_is_row_error() -> None:
    result = split_rows(lines(row("A", "U1", "S", ""), row("A", "U2", "T", "Term 1")), SPLIT, MERGE)
    assert [(e.row, e.column) for e in result.errors] == [(2, "term")]
    assert result.rows == []


def test_without_merge_column_rows_stay_separate() -> None:
    split = SPLIT.model_copy(update={"merge_column": None, "pair_column": None})
    result = split_rows(
        lines(row("A", "U1", "S", "Term 1"), row("B", "U2", "S", "Term 1")), split, MERGE
    )
    assert [r["group"] for _, r in result.rows] == ["A", "B"]


def test_preference_never_hides_a_value_outside_it() -> None:
    # "lab" is a typo, not a preferred value: the planner must hear about it.
    result = split_rows(
        lines(row("A", "U1", "S", "Term 1", room_type="lab"), row("B", "U2", "S", "Term 1")),
        SPLIT,
        MERGE,
    )
    assert result.rows == []
    [error] = result.errors
    assert error.column == "room_type" and "lab" in error.message


def test_a_pair_stays_in_one_term_when_one_unit_is_aligned_elsewhere() -> None:
    # G2's pair Q aligns subject T to Term 2; G1's pair P holds units of subjects S and T.
    result = split_rows(
        lines(
            row("G2", "C", "T", "Term 2", pair="Q"),
            row("G2", "D", "T", "Term 2", pair="Q"),
            row("G1", "A", "S", "Term 1", pair="P"),
            row("G1", "B", "T", "Term 1", pair="P"),
        ),
        SPLIT,
        MERGE,
    )
    kept = {(g, m["subject"]) for _, m in result.rows for g in m["group"].split(";")}
    assert (("G1", "S") in kept) == (("G1", "T") in kept), kept
