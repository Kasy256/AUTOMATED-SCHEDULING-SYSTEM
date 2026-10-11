import csv
import io
from dataclasses import dataclass


class CsvError(ValueError):
    pass


@dataclass(frozen=True)
class CsvTable:
    columns: tuple[str, ...]
    rows: tuple[tuple[int, dict[str, str]], ...]  # (CSV line number, cells by column)


def split_list(cell: str) -> list[str]:
    return [part.strip() for part in cell.split(";") if part.strip()]


def parse_csv(data: bytes, max_rows: int) -> CsvTable:
    """UTF-8 CSV (BOM tolerated) with one header row; cells are stripped strings."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvError("The file is not UTF-8 text") from exc
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if not header:
        raise CsvError("The file has no header row")
    columns = tuple(name.strip() for name in header)
    if any(not name for name in columns):
        raise CsvError("A column header is empty")
    if len(set(columns)) != len(columns):
        raise CsvError("The header has duplicate column names")
    rows: list[tuple[int, dict[str, str]]] = []
    for cells in reader:
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) == max_rows:
            raise CsvError(f"The file has more than {max_rows} rows")
        padded = [*cells, *[""] * (len(columns) - len(cells))]
        cells_by_column = {name: padded[i].strip() for i, name in enumerate(columns)}
        rows.append((reader.line_num, cells_by_column))
    return CsvTable(columns, tuple(rows))
