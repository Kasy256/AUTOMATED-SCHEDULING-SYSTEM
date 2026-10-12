from collections.abc import Iterable, Mapping, Sequence

from cartlyf_api.errors import FieldError, field_error
from cartlyf_api.imports.schemas import ImportReport, RowError
from cartlyf_engine.precheck import Issue

# Keeps stored reports small; error_count still says how many there were.
MAX_REPORTED_ERRORS = 500


def report_of(
    row_count: int,
    created: int,
    errors: Sequence[RowError],
    feasibility: Iterable[Issue] = (),
    skipped: int = 0,
) -> ImportReport:
    return ImportReport(
        skipped=skipped,
        valid=not errors,
        row_count=row_count,
        created=created,
        errors=list(errors[:MAX_REPORTED_ERRORS]),
        error_count=len(errors),
        feasibility=list(feasibility),
    )


def missing_column_errors(
    mapping_columns: Mapping[str, str | None], columns: Sequence[str]
) -> list[FieldError]:
    """422 errors for mapped columns the file does not have; keys are dotted mapping paths."""
    present = set(columns)
    return [
        field_error(
            ("body", "mapping", *(int(p) if p.isdigit() else p for p in key.split("."))),
            f"The file has no column named '{column}'",
        )
        for key, column in mapping_columns.items()
        if column is not None and column not in present
    ]
