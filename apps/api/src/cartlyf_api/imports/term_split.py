"""Term split for session-demand imports (ported from the legacy ISBAT term splitter).

Rows are one per (group, unit). A unit's term is, in order: the term its subject is aligned to
across programmes, the majority term of its theory/practical pair within the group, its own term.
Rows of the selected term are then merged per subject, so equivalent units become one demand.
"""

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cartlyf_api.imports.csv_table import split_list
from cartlyf_api.imports.schemas import RowError, TermSplit

Line = tuple[int, Mapping[str, str]]
_TERM = re.compile(r"(?:term\s*)?(\d+)")


@dataclass(frozen=True)
class MergeColumns:
    lists: set[str]  # `;` lists: the union, in first-seen order
    maxima: set[str]  # whole numbers: the largest
    attrs: dict[str, str]  # attribute key -> column; differing values resolved by preference
    agree: set[str]  # every merged row must hold the same value


@dataclass(frozen=True)
class SplitResult:
    rows: list[tuple[int, dict[str, str]]]
    errors: list[RowError]
    skipped: int


def term_number(cell: str) -> int | None:
    match = _TERM.fullmatch(cell.strip().lower())
    return int(match.group(1)) if match else None


def _most_common(terms: list[int]) -> int:
    # Counter keeps first-seen order on ties, as the legacy splitter did.
    return Counter(terms).most_common(1)[0][0]


def _resolve_terms(lines: Sequence[Line], split: TermSplit, own: list[int]) -> list[int]:
    def cell(record: Mapping[str, str], column: str | None) -> str:
        return record.get(column, "") if column else ""

    pair_terms: dict[tuple[str, str], list[int]] = {}
    for (_, record), term in zip(lines, own, strict=True):
        if pair := cell(record, split.pair_column):
            pair_terms.setdefault((record[split.group_column], pair), []).append(term)
    pair_term = {key: _most_common(terms) for key, terms in pair_terms.items()}

    units: dict[str, set[str]] = {}
    votes: dict[str, list[int]] = {}
    from_pair: dict[str, int] = {}
    for (_, record), term in zip(lines, own, strict=True):
        if not (subject := cell(record, split.merge_column)):
            continue
        units.setdefault(subject, set()).add(record[split.unit_column])
        votes.setdefault(subject, []).append(term)
        key = (record[split.group_column], cell(record, split.pair_column))
        if key in pair_term:
            from_pair.setdefault(subject, pair_term[key])
    aligned = {
        subject: from_pair.get(subject, _most_common(votes[subject]))
        for subject, codes in units.items()
        if len(codes) > 1
    }

    resolved: list[int] = []
    for (_, record), term in zip(lines, own, strict=True):
        subject = cell(record, split.merge_column)
        key = (record[split.group_column], cell(record, split.pair_column))
        resolved.append(aligned.get(subject) or pair_term.get(key) or term)
    return resolved


def _merge(
    group: list[Line], split: TermSplit, merge: MergeColumns
) -> tuple[dict[str, str], list[RowError]]:
    first_line, first = group[0]
    merged = dict(first)
    errors: list[RowError] = []
    for column in merge.lists:
        values = [v for _, r in group for v in split_list(r.get(column, ""))]
        merged[column] = ";".join(dict.fromkeys(values))
    for column in merge.maxima:
        texts = [r.get(column, "") for _, r in group]
        # An unreadable cell is kept so the demand row check reports it with the other errors.
        unreadable = [t for t in texts if not t.strip().isdigit()]
        merged[column] = unreadable[0] if unreadable else str(max(int(t) for t in texts))
    disagreeing = [(c, None) for c in merge.agree] + [(c, key) for key, c in merge.attrs.items()]
    for column, key in disagreeing:
        values = list(dict.fromkeys(r.get(column, "") for _, r in group))
        if len(values) == 1:
            continue
        preferred = [v for v in split.prefer.get(key, []) if v in values] if key else []
        if preferred:
            merged[column] = preferred[0]
        else:
            message = f"Merged rows disagree on '{column}': {', '.join(sorted(values))}"
            errors.append(RowError(row=first_line, column=column, message=message))
    return merged, errors


def split_rows(lines: Sequence[Line], split: TermSplit, merge: MergeColumns) -> SplitResult:
    """Keep the selected term's rows and merge them per subject; errors stop the merge."""
    own: list[int] = []
    errors: list[RowError] = []
    for line, record in lines:
        term = term_number(record.get(split.term_column, ""))
        if term is None:
            message = "Missing or unreadable term"
            errors.append(RowError(row=line, column=split.term_column, message=message))
        own.append(term or 0)
    if errors:
        return SplitResult([], errors, 0)

    wanted = term_number(split.term)
    resolved = _resolve_terms(lines, split, own)
    kept = [line for line, term in zip(lines, resolved, strict=True) if term == wanted]
    groups: dict[str, list[Line]] = {}
    for index, (line, record) in enumerate(kept):
        subject = record.get(split.merge_column, "") if split.merge_column else ""
        groups.setdefault(subject or f"#{index}", []).append((line, record))

    rows: list[tuple[int, dict[str, str]]] = []
    for group in groups.values():
        merged, group_errors = _merge(group, split, merge)
        errors += group_errors
        rows.append((group[0][0], merged))
    if errors:
        return SplitResult([], errors, len(lines) - len(kept))
    return SplitResult(rows, [], len(lines) - len(kept))
