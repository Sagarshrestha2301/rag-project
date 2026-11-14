"""Prove the table chunker: caption, units, footnotes, splitting, no duplicates.

The duplication case is the important one: it checks that a table's cells land in
exactly one chunk, so retrieval cannot return the same table twice with different
framing.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_tables.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import build, structure, tables            # noqa: E402
from chunk.base import DocMeta                        # noqa: E402

PARSED = pathlib.Path("index/parsed/pages.jsonl")
FAILURES: list[str] = []
META = DocMeta(file="1970_Test_W1.pdf", year=1970, publisher="Banko Janakari")


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


class Page:
    def __init__(self, number, blocks, rects, tables_=None, text=""):
        self.pdf_page = number
        self.blocks = blocks
        self.block_rects = rects
        self.tables = tables_ or []
        self.text = text


def table_page(rows, bbox=(50, 120, 500, 300), caption_rect=(50, 100, 500, 112)):
    """A page with a caption above a table and a 'Key:' note below it."""
    return Page(
        number=1,
        blocks=["Table-1: Beliefs about bamboo (%)", "1 2\n3 4", "Key: HH =household"],
        rects=[caption_rect, (50, 130, 500, 290), (50, 305, 500, 317)],
        tables_=[{"rows": rows, "bbox": list(bbox), "parser": "pymupdf-grid+words",
                  "headers_from": "cells", "notes": []}],
    )


# --- caption, units, footnotes -------------------------------------------

def caption_found_above_bbox():
    chunks, _ = tables.chunks_for_document([table_page([["A", "B"], ["1", "2"]])], META)
    assert len(chunks) == 1, len(chunks)
    assert chunks[0].caption == "Table-1: Beliefs about bamboo (%)", chunks[0].caption
    assert "Table 1: Table-1: Beliefs" in chunks[0].text, chunks[0].text.splitlines()[0]


def units_from_header_cells():
    chunks, _ = tables.chunks_for_document(
        [table_page([["Weak (%)", "Years"], ["1", "2"]])], META)
    assert chunks[0].units == "%", chunks[0].units
    assert "units: %" in chunks[0].text


def footnote_below_bbox():
    chunks, _ = tables.chunks_for_document([table_page([["A"], ["1"]])], META)
    assert chunks[0].footnotes == ["Key: HH =household"], chunks[0].footnotes
    assert "notes: Key: HH =household" in chunks[0].text


def missing_caption_is_recorded_not_invented():
    page = table_page([["A"], ["1"]])
    page.blocks = ["1 2", "nothing above this table"]
    page.block_rects = [(50, 130, 500, 290), (50, 305, 500, 317)]
    chunks, _ = tables.chunks_for_document([page], META)
    assert chunks[0].caption == "", chunks[0].caption
    assert "no caption found above bbox" in chunks[0].notes, chunks[0].notes


def cells_are_verbatim():
    chunks, _ = tables.chunks_for_document([table_page([["p", "q"], ["69.85", "0.48"]])], META)
    assert "| 69.85 | 0.48 |" in chunks[0].text, chunks[0].text


# --- long tables ---------------------------------------------------------

def long_table_splits_with_repeated_header():
    rows = [["Year", "Value"]] + [[str(1900 + n), str(n)] for n in range(60)]
    chunks, _ = tables.chunks_for_document([table_page(rows)], META)
    assert len(chunks) == 4, len(chunks)
    for chunk in chunks:
        assert "| Year | Value |" in chunk.text, "header row must repeat"
        assert "rows " in chunk.text, chunk.text.splitlines()[0]
    assert "(rows 1-15 of 60)" in chunks[0].text
    assert "(rows 16-30 of 60)" in chunks[1].text


def short_table_is_one_chunk():
    chunks, _ = tables.chunks_for_document([table_page([["A"], ["1"]])], META)
    assert len(chunks) == 1


# --- exclusion from text chunks -----------------------------------------

def blocks_inside_bbox_are_excluded_from_text():
    page = table_page([["A"], ["1"]])
    _, skip = tables.chunks_for_document([page], META)
    # Block 1 sits inside the bbox and block 2 is its "Key:" note; the caption stays.
    assert skip == frozenset({1, 2}), skip
    assert 0 not in skip, "the caption must stay available as text"


def table_text_outside_bbox_is_still_excluded():
    """Das p2/p9 put table text in blocks the detected bbox does not cover."""
    page = table_page([["Weak", "Years"], ["69.85", "37.96"]])
    page.blocks = page.blocks + ["69.85 37.96 Weak Years"]
    page.block_rects = page.block_rects + [(50, 320, 500, 340)]
    _, skip = tables.chunks_for_document([page], META)
    assert 3 in skip, f"table-word block not excluded: {skip}"


def stats_row_with_cell_numbers_is_excluded():
    """Das p9: cells plus a Chi-Square note in one block."""
    page = table_page([["Weak", "Years"], ["30.15", "69.85"]])
    page.blocks = page.blocks + [
        "30.15 / 69.85 / Chi-Square = 5.071, DF = 1, P-Value = 0.024"]
    page.block_rects = page.block_rects + [(50, 320, 500, 340)]
    _, skip = tables.chunks_for_document([page], META)
    assert 3 in skip, f"mixed stats row not excluded: {skip}"


def prose_quoting_one_number_is_not_excluded():
    page = table_page([["Weak", "Years"], ["69.85", "37.96"]])
    page.blocks = page.blocks + [
        "Growers in the eastern hills reported that the practice had declined "
        "over the decade, reaching 69.85 percent of households in the survey."]
    page.block_rects = page.block_rects + [(50, 320, 500, 340)]
    _, skip = tables.chunks_for_document([page], META)
    assert 3 not in skip, "a prose block quoting one table number was excluded"


def real_corpus_no_table_is_embedded_twice():
    for doc, pages in _corpus().items():
        chunks = build.chunks_for_document(pages, DocMeta(file=doc, year=1970))
        table_chunks = [chunk for chunk in chunks if chunk.type == "table"]
        text_chunks = [chunk for chunk in chunks if chunk.type == "text"]
        table_blocks = {index for chunk in table_chunks for index in chunk.block_indices}
        text_blocks = {index for chunk in text_chunks for index in chunk.block_indices}
        assert not (table_blocks & text_blocks), (
            f"{doc}: {len(table_blocks & text_blocks)} block(s) used by both chunkers")


def real_corpus_has_all_nine_tables_once():
    total = 0
    captions = 0
    for doc, pages in _corpus().items():
        chunks = [c for c in build.chunks_for_document(pages, DocMeta(file=doc))
                  if c.type == "table"]
        total += len(chunks)
        captions += sum(1 for chunk in chunks if chunk.caption)
        for chunk in chunks:
            assert chunk.block_indices, f"{doc}: table chunk without source blocks"
    assert total == 9, f"{total} table chunks, expected 9"
    assert captions == 5, f"{captions} captions recovered, expected 5"


def real_corpus_each_table_rendered_once():
    """Every detected table becomes exactly one table chunk, and no cell text
    is also emitted as prose.

    Deliberately not a "this number appears once" test: Ahasan's prose quotes its
    own correlation values (`36.69` in five paragraphs) and `69.85` occurs in two
    different Das tables, so both would fail for correct reasons. The duplication
    that matters is a *block* feeding both chunkers, and that is asserted
    separately by `real_corpus_no_table_is_embedded_twice`.
    """
    for doc, pages in _corpus().items():
        detected = sum(len(page.tables) for page in pages)
        chunks = build.chunks_for_document(pages, DocMeta(file=doc))
        rendered = [chunk for chunk in chunks if chunk.type == "table"]
        assert len(rendered) == detected, (
            f"{doc}: {len(rendered)} table chunks for {detected} detected tables")
        assert len({chunk.chunk_id for chunk in rendered}) == len(rendered)
        for chunk in rendered:
            body_lines = chunk.text.splitlines()
            assert body_lines[0].startswith("Table "), body_lines[0]
            assert any(line.startswith("|") for line in body_lines), chunk.chunk_id


def real_corpus_ids_unique_and_ordered():
    for doc, pages in _corpus().items():
        chunks = build.chunks_for_document(pages, DocMeta(file=doc))
        ids = [chunk.chunk_id for chunk in chunks]
        assert len(set(ids)) == len(ids), f"{doc}: duplicate chunk ids"
        pages_seen = [chunk.page_start for chunk in chunks]
        assert pages_seen == sorted(pages_seen), f"{doc}: chunks not in page order"


def _corpus() -> dict[str, list]:
    docs: dict[str, list] = {}
    for line in PARSED.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        docs.setdefault(record["doc"], []).append(Page(
            record["pdf_page"], record["blocks"], record["block_rects"],
            record["tables"], record["text"]))
    for pages in docs.values():
        pages.sort(key=lambda page: page.pdf_page)
    return docs


def main() -> int:
    print("caption, units, footnotes")
    for name, fn in [("caption found above the bbox", caption_found_above_bbox),
                     ("units taken from the header cells", units_from_header_cells),
                     ("footnote below the bbox is kept", footnote_below_bbox),
                     ("a missing caption is recorded, not invented",
                      missing_caption_is_recorded_not_invented),
                     ("cells are emitted verbatim", cells_are_verbatim)]:
        check(name, fn)

    print("splitting")
    for name, fn in [("a short table is one chunk", short_table_is_one_chunk),
                     ("a long table splits, header repeated",
                      long_table_splits_with_repeated_header)]:
        check(name, fn)

    print("no table is embedded twice")
    for name, fn in [("blocks inside the bbox are skipped by the text chunker",
                      blocks_inside_bbox_are_excluded_from_text),
                     ("table text outside the bbox is excluded too",
                      table_text_outside_bbox_is_still_excluded),
                     ("a stats row carrying cell numbers is excluded",
                      stats_row_with_cell_numbers_is_excluded),
                     ("prose quoting one table number is kept",
                      prose_quoting_one_number_is_not_excluded),
                     ("real corpus: no block used by both chunkers",
                      real_corpus_no_table_is_embedded_twice),
                     ("real corpus: all 9 tables, 5 captions",
                      real_corpus_has_all_nine_tables_once),
                     ("real corpus: each table is rendered exactly once",
                      real_corpus_each_table_rendered_once),
                     ("real corpus: ids unique and in page order",
                      real_corpus_ids_unique_and_ordered)]:
        check(name, fn)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
