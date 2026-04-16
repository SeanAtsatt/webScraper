# tests/unit/parse/test_tables.py
"""Table extraction tests."""

from webscraper.parse.tables import extract_tables


def test_extract_tables_with_thead() -> None:
    html = """
    <table>
      <thead><tr><th>Name</th><th>Email</th></tr></thead>
      <tbody>
        <tr><td>Alice</td><td>a@x</td></tr>
        <tr><td>Bob</td><td>b@x</td></tr>
      </tbody>
    </table>
    """
    tables = extract_tables(html)
    assert len(tables) == 1
    assert tables[0].headers == ["Name", "Email"]
    assert tables[0].rows == [["Alice", "a@x"], ["Bob", "b@x"]]


def test_extract_tables_without_thead_uses_first_row_of_th() -> None:
    html = """
    <table>
      <tr><th>A</th><th>B</th></tr>
      <tr><td>1</td><td>2</td></tr>
    </table>
    """
    tables = extract_tables(html)
    assert tables[0].headers == ["A", "B"]
    assert tables[0].rows == [["1", "2"]]


def test_extract_tables_empty_when_no_tables() -> None:
    assert extract_tables("<p>no tables</p>") == []
