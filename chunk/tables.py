"""Table chunks: one table, one chunk, with the caption that makes it findable.

A table split across two chunks answers nothing — half a table is a wrong answer —
so a table is one chunk unless it is genuinely long, and then it splits by row
groups with the header repeated.

What has to be recovered from the page, because Step 3 stores cells but not
these (measured: caption present for 5 of 9 tables):

* **caption** — the nearest block *above* the table's bbox, within 60 pt, whose
  first line matches `(?i)^table[\\s\\-–]?\\d+`. Three styles occur here:
  `Table-1: List of the El Nino…`, `Table 2 Level of beliefs…`,
  `Table-3: Correlation coefficients…`. No caption is ever invented: when nothing
  matches, `caption` stays empty and `notes` says so.
* **units** — from a parenthetical in the header cells (`(%)`, `(mm)`) or from
  the caption. Recorded as a string, `""` when absent, because Das's tables mix
  a count with two percentages.
* **footnotes** — blocks below the bbox within 60 pt starting with `*`, `†`,
  `‡`, `Note`, `Source` or `Key` (Das p3 really does have `Key: HH =household`).

Cells are emitted exactly as Step 3 verified them against the page's words. The
chunker never reformats a number, never parses a cell, and never guesses a split
for Das p9's merged sub-columns; it records the defect in `notes` instead.

Usage:
    from chunk.base import DocMeta
    from chunk.tables import chunks_for_document
    chunks, skip = chunks_for_document(pages, DocMeta(file="x.pdf"))
    chunks[0].text.splitlines()[:2]
    # ['Table 1: List of the El Nino and La Nina years', 'units: none']
"""

from __future__ import annotations

import re

from chunk import structure
from chunk.base import Block, Chunk, DocMeta, register_chunker

CAPTION = re.compile(r"(?i)^table[\s\-–]?\d+")
NOTE_LINE = re.compile(r"(?i)^(\*|†|‡|note|source|key)\b")
# Das p9 puts `30.15 / 69.85 / Chi-Square = 5.071, DF = 1, P-Value = 0.024`
# 3 pt below table 1's bbox: a statistics note, not a cell. Without this it became
# its own text chunk and 69.85 was embedded twice.
STATS_NOTE = re.compile(r"(?i)(chi[\s\-]?square|p[\s\-]?value|\bdf\s*=)")
UNITS = re.compile(r"\(([^)]{1,12})\)")

MAX_ROWS = 25          # a table longer than this splits into row groups
ROW_GROUP = 15
MAX_CHARS = 1_500
CAPTION_WINDOW = 60.0  # points above the bbox to look for the caption


@register_chunker("table")
class TableChunker:
    """Renders each table as markdown with its caption, units and notes."""

    name = "table"

    def chunks(self, page, meta: DocMeta, *, start_seq: int = 0):
        """(chunks, block indices to exclude from text chunks) for one page."""
        pairs = _blocks_with_rects(page)
        chunks: list[Chunk] = []
        skip: set[int] = set()

        for number, table in enumerate(_tables(page), start=1):
            bbox = tuple(table["bbox"])
            inside = [position for position, _, rect in pairs if _inside(rect, bbox)]
            skip.update(inside)
            caption = _caption(pairs, bbox)
            units = _units(table["rows"], caption)
            footnotes, footnoted = _footnotes(pairs, bbox)
            skip.update(footnoted)      # a note belongs to the table, not to prose
            notes = list(table.get("notes") or [])
            if not caption:
                notes.append("no caption found above bbox")

            for part, rows, label in _parts(table["rows"], table.get("headers_from")):
                chunks.append(Chunk(
                    chunk_id=f"{_stem(meta.file)}:p{page.pdf_page}:t{number}{part}",
                    file=meta.file,
                    page_start=page.pdf_page,
                    page_end=page.pdf_page,
                    section_path=[],          # filled in by chunk.build
                    text=_render(number, rows, caption, units, footnotes, label),
                    type="table",
                    caption=caption,
                    units=units,
                    footnotes=footnotes,
                    notes=notes,
                    block_indices=sorted(inside),   # page-local; translated in chunks_for_document
                    year=meta.year,
                    publisher=meta.publisher,
                    doc_type=meta.doc_type,
                    doc_context=meta.doc_context,
                ))
        return chunks, frozenset(skip)


def chunks_for_document(pages, meta: DocMeta):
    """All table chunks of one document, plus the block indices they consumed.

    ``skip`` is a superset of the blocks inside a bbox, because the detected bbox
    does not always cover the whole table: Das p2 and p9 have table text in
    blocks outside any bbox, and without the content test `69.85` ended up in
    **three** chunks (two text, one table) instead of one.

    Usage:
        chunks, skip = chunks_for_document(pages, meta)
        len(chunks)          # 9 for this corpus
        len(skip)            # blocks that must not become text chunks
    """
    chunker = TableChunker()
    chunks: list[Chunk] = []
    skip: set[int] = set()
    # Block positions are page-local, but the text chunker filters on
    # document-level indices. Without this translation the exclusion silently
    # missed on every page after the first, and 69.85 stayed in two text chunks.
    index_of = {(block.pdf_page, block.page_block): block.index
                for block in structure.document_blocks(pages)}

    for page in pages:
        found, consumed = chunker.chunks(page, meta, start_seq=len(chunks))
        local = set(consumed) | _table_text_blocks(page)
        for position in local:
            index = index_of.get((page.pdf_page, position))
            if index is not None:
                skip.add(index)
        for chunk in found:
            positions = list(chunk.block_indices)   # still page-local here
            chunk.block_indices = sorted(
                index_of[(page.pdf_page, position)] for position in positions
                if (page.pdf_page, position) in index_of)
        chunks.extend(found)
    return chunks, frozenset(skip)


def _table_text_blocks(page) -> set[int]:
    """Blocks outside every bbox whose text is mostly table cells.

    Two signals, because one is not enough. Word overlap ≥60% catches a block that
    is pure cells. A numeric rule catches the mixed case: Das p9 has a block that
    is `30.15 / 69.85 / Chi-Square = 5.071, DF = 1, P-Value = 0.024`, which is
    table content with a statistics note attached — only 7% of its words are cell
    words, but 2 of its numbers are cell numbers. Prose that quotes one table
    figure still fails both tests and stays as text.
    """
    rows = [row for table in _tables(page) for row in (table.get("rows") or [])]
    cells = {token for row in rows for cell in row
             for token in re.findall(r"\w+", str(cell).lower())}
    cell_numbers = {number for row in rows for cell in row
                    for number in _numbers(str(cell))}
    if not cells:
        return set()

    found = set()
    for position, text, _ in _blocks_with_rects(page):
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            continue
        # A heading must survive even when every word in it also appears in a
        # cell: Das p9's blocks `21.84` and `Nongrowers` are one token each, and
        # without this guard a section number would be eaten as table content.
        if structure.parse_heading(Block(page.pdf_page, text, -1), first_page=0):
            continue
        if sum(1 for token in tokens if token in cells) / len(tokens) >= 0.6:
            found.add(position)
            continue

        numbers = _numbers(text)
        repeated = [number for number in numbers if number in cell_numbers]
        if len(repeated) >= 2 and len(repeated) / len(numbers) >= 0.4:
            found.add(position)
    return found


def _numbers(text: str) -> list[str]:
    """Numbers as whole tokens: `69.85` stays one number, not 69 and 85."""
    return re.findall(r"\d+(?:[.,]\d+)*", text)


# --- caption, units, footnotes -------------------------------------------

def _caption(pairs, bbox) -> str:
    best = None
    for _, text, rect in pairs:
        if rect[3] > bbox[1] + 2 or bbox[1] - rect[3] > CAPTION_WINDOW:
            continue
        first = text.splitlines()[0].strip()
        if CAPTION.match(first) and (best is None or rect[3] > best[0]):
            best = (rect[3], text.strip())
    return best[1].replace("\n", " ") if best else ""


def _units(rows, caption: str) -> str:
    for row in rows[:1]:
        for cell in row:
            match = UNITS.search(cell)
            if match and not match.group(1).strip().replace(".", "").isdigit():
                return match.group(1).strip()
    if caption:
        match = UNITS.search(caption)
        if match:
            return match.group(1).strip()
    return ""


def _footnotes(pairs, bbox) -> tuple[list[str], set[int]]:
    """(note lines below the table, block positions those notes came from)."""
    found: list[str] = []
    positions: set[int] = set()
    for position, text, rect in pairs:
        if rect[1] < bbox[3] - 2 or rect[1] - bbox[3] > CAPTION_WINDOW:
            continue
        stripped = text.strip()
        if NOTE_LINE.match(stripped) or STATS_NOTE.search(stripped):
            found.append(stripped.replace("\n", " "))
            positions.add(position)
    return found, positions


# --- rendering ------------------------------------------------------------

def _render(number: int, rows: list[list[str]], caption: str, units: str,
            footnotes: list[str], label: str) -> str:
    head = f"Table {number}: {caption}" if caption else f"Table {number} (no caption found)"
    if label:
        head += f" {label}"
    lines = [head, f"units: {units or 'none'}", ""]
    width = max((len(row) for row in rows), default=0)
    for position, row in enumerate(rows):
        cells = [_cell(cell) for cell in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if position == 0:
            lines.append("|" + "---|" * width)
    for note in footnotes:
        lines.append(f"notes: {note}")
    return "\n".join(lines)


def _cell(value: str) -> str:
    """A cell exactly as extracted, with pipes escaped for markdown."""
    return (value or "").replace("|", "\\|").strip()


def _parts(rows: list[list[str]], headers_from: str | None):
    """(suffix, rows, label) per chunk: one part, or row groups with a header."""
    body = rows[1:] if (headers_from or "cells") == "cells" and len(rows) > 1 else rows
    chars = sum(len(cell) for row in rows for cell in row)
    if len(body) <= MAX_ROWS and chars <= MAX_CHARS:
        return [("", rows, "")]

    header = rows[:1] if body is not rows else []
    parts = []
    total = len(body)
    for start in range(0, total, ROW_GROUP):
        group = body[start:start + ROW_GROUP]
        label = f"(rows {start + 1}-{start + len(group)} of {total})"
        parts.append((f"-{start // ROW_GROUP + 1}", header + group, label))
    return parts


# --- geometry helpers -----------------------------------------------------

def _blocks_with_rects(page):
    rects = getattr(page, "block_rects", []) or []
    return [(position, text, rect) for position, (text, rect)
            in enumerate(zip(page.blocks, rects)) if rect]


def _inside(rect, bbox) -> bool:
    cx = (rect[0] + rect[2]) / 2
    cy = (rect[1] + rect[3]) / 2
    return bbox[0] - 1 <= cx <= bbox[2] + 1 and bbox[1] - 1 <= cy <= bbox[3] + 1


def _tables(page) -> list[dict]:
    return [table if isinstance(table, dict) else table.as_dict()
            for table in (getattr(page, "tables", []) or [])]


def _stem(file: str) -> str:
    return file[:-4] if file.lower().endswith(".pdf") else file
