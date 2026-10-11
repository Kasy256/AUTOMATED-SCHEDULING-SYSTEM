import pytest

from cartlyf_api.imports.csv_table import CsvError, parse_csv, split_list


def test_parses_headers_and_rows_with_bom_and_quotes() -> None:
    table = parse_csv('﻿Code, Name ,Tags\nL1,"Okello, A",a;b\nL2,B,\n'.encode(), 100)
    assert table.columns == ("Code", "Name", "Tags")
    assert table.rows == (
        (2, {"Code": "L1", "Name": "Okello, A", "Tags": "a;b"}),
        (3, {"Code": "L2", "Name": "B", "Tags": ""}),
    )


def test_row_numbers_are_csv_line_numbers() -> None:
    table = parse_csv(b"Code\nA\n\nB\n", 10)
    assert [line for line, _ in table.rows] == [2, 4]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"\xff\xfe\x00", "UTF-8"),
        (b"", "header"),
        (b"Code,Code\nA,B\n", "duplicate"),
        (b"Code,\nA,B\n", "empty"),
        (b"Code\n" + b"A\n" * 3, "more than 2 rows"),
    ],
)
def test_rejects_bad_files(data: bytes, message: str) -> None:
    with pytest.raises(CsvError, match=message):
        parse_csv(data, 2)


def test_split_list() -> None:
    assert split_list(" a; b ;;c ") == ["a", "b", "c"]
    assert split_list("") == []
