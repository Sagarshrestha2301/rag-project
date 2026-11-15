"""Table extraction for Step 3, in two cases (see STEP3-PLAN.md section 3).

Case A (preferred): PyMuPDF `find_tables` finds the table (Das pages 2, 3 and
        6, and nearly every table in this corpus). Its *geometry* is right but
        its cell text is damaged: the cell holding 69.85 comes back as
        "6985\\n.". So the grid is taken from PyMuPDF and the text is taken from
        the page's own word list, where "69.85" is a single token. Nothing is
        repaired after the fact; the correct value is the one that was never
        corrupted.

Case B (fallback): PyMuPDF finds no table and pdfplumber does -> use
        pdfplumber's cells. Measured clean on the Ahasan tables and on Das
        page 9.

The note on each table says which check was made, never both: "pdfplumber
agrees a table is here", "pdfplumber found no table here", or "pdfplumber could
not read this page". An earlier version wrote the first note in the grid
builder and the second in the comparison, so 97 tables said both at once.

Usage:
    from ingest.tables import detect, page_tables
    found = detect(pdf_page=pymupdf_page)
    tables = page_tables(pdf_page=pymupdf_page, pdfplumber_page=pl_page)
"""

from __future__ import annotations

import statistics

import pymupdf

from ingest.base import Table

NUMERIC_HINTS = set("0123456789.,%-–")


def _words(page) -> list[tuple]:
    return page.get_text("words")   # x0, y0, x1, y1, word, block, line, word_no


def _centre_inside(word: tuple, rect: pymupdf.Rect) -> bool:
    cx = (word[0] + word[2]) / 2
    cy = (word[1] + word[3]) / 2
    return rect.contains(pymupdf.Point(cx, cy))


def _cell_text(words: list[tuple], cell: tuple) -> str:
    """Words whose centre falls inside the cell, left to right, top to bottom."""
    rect = pymupdf.Rect(cell)
    inside = [w for w in words if _centre_inside(w, rect)]
    inside.sort(key=lambda w: (round(w[1], 1), w[0]))
    return " ".join(w[4] for w in inside)


def detect(*, pdf_page) -> list:
    """Tables PyMuPDF can locate on this page (possibly with damaged text)."""
    try:
        found = pdf_page.find_tables()
    except Exception:  # noqa: BLE001 - a detection failure must not stop the run
        return []
    return list(getattr(found, "tables", []) or [])


def from_pymupdf_grid(*, pdf_page, table) -> Table | None:
    """Case B: PyMuPDF's cell boxes, the page's own words."""
    if not getattr(table, "rows", None):
        return None
    words = _words(pdf_page)
    rows: list[list[str]] = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cells.append("" if cell is None else _cell_text(words, cell))
        rows.append(cells)
    if not rows:
        return None
    return Table(rows=rows, bbox=tuple(table.bbox), parser="pymupdf-grid+words")


def from_pdfplumber(*, pdfplumber_page, index: int) -> Table | None:
    """Case A: pdfplumber's own cells."""
    try:
        found = pdfplumber_page.find_tables()
    except Exception:  # noqa: BLE001
        return None
    if not found:
        return None
    found = sorted(found, key=lambda t: (t.bbox[1], t.bbox[0]))
    if index >= len(found):
        return None
    table = found[index]
    try:
        rows = table.extract()
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    clean = [["" if c is None else " ".join(str(c).split()) for c in row] for row in rows]
    return Table(rows=clean, bbox=tuple(table.bbox), parser="pdfplumber")


def page_tables(*, pdf_page, pdfplumber_page) -> list[Table]:
    """All tables on a page.

    Preference is PyMuPDF's grid filled from the page's own words, because that
    is the only path that keeps `69.85` intact. pdfplumber is the fallback for a
    page PyMuPDF cannot see a table on at all.
    """
    detected = detect(pdf_page=pdf_page)
    out: list[Table] = []
    for i, table in enumerate(detected):
        assembled = from_pymupdf_grid(pdf_page=pdf_page, table=table)
        if assembled is None:
            continue
        # One note, decided by the comparison. This used to add "pdfplumber
        # found no table here" in the builder and "pdfplumber agrees" here, so a
        # table both parsers saw carried both notes.
        if pdfplumber_page is None:
            assembled.notes.append("pdfplumber could not read this page")
        elif from_pdfplumber(pdfplumber_page=pdfplumber_page, index=i) is not None:
            assembled.notes.append("pdfplumber agrees a table is here")
        else:
            assembled.notes.append("pdfplumber found no table here")
        out.append(assembled)

    if not out and pdfplumber_page is not None:
        only = from_pdfplumber(pdfplumber_page=pdfplumber_page, index=0)
        if only is not None:
            only.notes.append("PyMuPDF found no table; pdfplumber did")
            out.append(only)
    return out


def numeric_cells(table: Table) -> list[str]:
    """Every number-looking token in the table, one per token.

    Tokens rather than whole cells on purpose: Das page 9 legitimately holds three
    values per cell (`19 21.84 31.67` = Count, % of row, % of column), and the
    check that matters is whether each value survived, not how the grid grouped it.
    """
    hits = []
    for row in table.rows:
        for cell in row:
            for token in cell.split():
                if token[0] in NUMERIC_HINTS and any(ch.isdigit() for ch in token):
                    hits.append(token)
    return hits


def cell_accuracy(table: Table, expected: list[str]) -> tuple[int, list[str]]:
    """How many expected numeric tokens appear verbatim in the table."""
    seen = set(numeric_cells(table))
    missing = [value for value in expected if value not in seen]
    return len(expected) - len(missing), missing


def median_height(words: list[tuple]) -> float:
    return statistics.median(w[3] - w[1] for w in words) if words else 0.0
