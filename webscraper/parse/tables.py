# webscraper/parse/tables.py
"""Extract <table> elements into TableSpec."""

from selectolax.parser import HTMLParser, Node

from webscraper.envelope import TableSpec


def _cells(row: Node, tag: str) -> list[str]:
    return [c.text(strip=True) for c in row.css(tag)]


def extract_tables(html: str) -> list[TableSpec]:
    tree = HTMLParser(html)
    out: list[TableSpec] = []
    for table in tree.css("table"):
        headers: list[str] = []
        rows: list[list[str]] = []
        thead = table.css_first("thead")
        if thead is not None:
            first_row = thead.css_first("tr")
            if first_row is not None:
                headers = _cells(first_row, "th") or _cells(first_row, "td")
            body_rows = table.css("tbody tr")
        else:
            all_rows = table.css("tr")
            if all_rows and all_rows[0].css("th"):
                headers = _cells(all_rows[0], "th")
                body_rows = all_rows[1:]
            else:
                body_rows = all_rows
        for row in body_rows:
            rows.append(_cells(row, "td"))
        out.append(TableSpec(headers=headers, rows=rows))
    return out
