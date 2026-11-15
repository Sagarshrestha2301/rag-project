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
    assert "no caption found within 160 pt of bbox" in chunks[0].notes, chunks[0].notes


def caption_below_the_table():
    page = Page(
        number=1,
        blocks=["Some prose about the study area.", "1 2\n3 4", "Table 3 – Yield by year"],
        rects=[(50, 60, 500, 100), (50, 130, 500, 290), (50, 305, 500, 340)],
        tables_=[{"rows": [["A"], ["1"]], "bbox": [50, 120, 500, 300],
                  "parser": "pymupdf-grid+words", "headers_from": "cells", "notes": []}],
    )
    chunks, _ = tables.chunks_for_document([page], META)
    assert chunks[0].caption == "Table 3 – Yield by year", chunks[0].caption
    assert "caption printed below the table" in chunks[0].notes, chunks[0].notes


def caption_style_table_no():
    page = table_page([["A"], ["1"]])
    page.blocks[0] = "Table No. 2: HDI of rural and urban regions"
    chunks, _ = tables.chunks_for_document([page], META)
    assert chunks[0].caption == "Table No. 2: HDI of rural and urban regions", chunks[0].caption


def far_caption_only_when_nothing_between():
    far = Page(
        number=1,
        blocks=["Table 2. Source of digital data.", "1 2", "x"],
        rects=[(50, 40, 500, 52), (50, 210, 500, 290), (50, 305, 500, 317)],
        tables_=[{"rows": [["A"], ["1"]], "bbox": [50, 200, 500, 300],
                  "parser": "pymupdf-grid+words", "headers_from": "cells", "notes": []}],
    )
    chunks, _ = tables.chunks_for_document([far], META)
    assert chunks[0].caption == "Table 2. Source of digital data.", chunks[0].caption

    blocked = Page(
        number=1,
        blocks=["Table 2. Source of digital data.", "Prose sits between them.", "1 2"],
        rects=[(50, 40, 500, 52), (50, 150, 500, 180), (50, 210, 500, 290)],
        tables_=[{"rows": [["A"], ["1"]], "bbox": [50, 200, 500, 300],
                  "parser": "pymupdf-grid+words", "headers_from": "cells", "notes": []}],
    )
    chunks, _ = tables.chunks_for_document([blocked], META)
    assert chunks[0].caption == "", f"stole a caption across prose: {chunks[0].caption!r}"


def units_collects_several_columns():
    chunks, _ = tables.chunks_for_document(
        [table_page([["Area (ha.)", "Share (%)"], ["1", "2"]])], META)
    assert "ha." in chunks[0].units and "%" in chunks[0].units, chunks[0].units


def units_ignore_non_units():
    chunks, _ = tables.chunks_for_document(
        [table_page([["Year (1996 and 2005)", "N"], ["1", "2"]])], META)
    assert "1996 and 2005" not in chunks[0].units, chunks[0].units


def note_further_below_is_kept():
    page = table_page([["A"], ["1"]])
    page.blocks.append("Notes: values are percentages of households")
    page.block_rects.append((50, 380, 500, 392))   # 80 pt below the bbox bottom (300)
    chunks, _ = tables.chunks_for_document([page], META)
    assert any("Notes:" in note for note in chunks[0].footnotes), chunks[0].footnotes


def short_prose_is_not_a_note():
    page = table_page([["A"], ["1"]])
    page.blocks.append("Values are taken from the district profile")
    page.block_rects.append((50, 305, 500, 317))
    chunks, _ = tables.chunks_for_document([page], META)
    assert chunks[0].footnotes == ["Key: HH =household"], chunks[0].footnotes


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


def real_corpus_has_every_detected_table():
    """Every detected table is rendered, with a caption or a note saying none was found.

    The grown corpus detects 169 tables; the Step 3 sample had 9. Four long
    tables split into row groups, so chunks can outnumber tables.
    """
    detected = 0
    rendered = 0
    captions = 0
    for doc, pages in _corpus().items():
        chunks = [chunk for chunk in build.chunks_for_document(pages, DocMeta(file=doc))
                  if chunk.type == "table"]
        expected = {(page.pdf_page, number) for page in pages
                    for number in range(1, len(page.tables) + 1)}
        got: dict[tuple[int, int], list] = {}
        for chunk in chunks:
            match = re.match(r"Table (\d+)", chunk.text.splitlines()[0])
            assert match, f"{doc}: {chunk.chunk_id} does not start with a table number"
            got.setdefault((chunk.page_start, int(match.group(1))), []).append(chunk)
            assert chunk.caption or "no caption found" in " ".join(chunk.notes), (
                f"{doc} {chunk.chunk_id}: no caption and no note")
        assert set(got) == expected, (
            f"{doc}: missing {sorted(set(expected) - set(got))}, "
            f"unexpected {sorted(set(got) - set(expected))}")
        detected += len(expected)
        rendered += len(chunks)
        captions += sum(1 for chunk in chunks if chunk.caption)
    assert detected >= 160, f"only {detected} tables detected in the grown corpus"
    assert rendered >= detected, (rendered, detected)


def real_corpus_split_tables_repeat_the_header():
    """A long table may split into row groups, but the header row and the row
    range are repeated in every part, and the parts tile the table exactly once."""
    splits = 0
    for doc, pages in _corpus().items():
        chunks = [chunk for chunk in build.chunks_for_document(pages, DocMeta(file=doc))
                  if chunk.type == "table"]
        groups: dict[tuple[int, int], list] = {}
        for chunk in chunks:
            match = re.match(r"Table (\d+)", chunk.text.splitlines()[0])
            groups.setdefault((chunk.page_start, int(match.group(1))), []).append(chunk)
        for (page, number), group in groups.items():
            assert len({chunk.chunk_id for chunk in group}) == len(group), group
            if len(group) == 1:
                continue
            splits += 1
            ranges = []
            headers = set()
            for chunk in group:
                head = chunk.text.splitlines()[0]
                match = re.search(r"\(rows (\d+)-(\d+) of (\d+)\)", head)
                assert match, f"{doc} p{page} t{number}: no row label in {head!r}"
                ranges.append(tuple(int(value) for value in match.groups()))
                headers.add(next(line for line in chunk.text.splitlines()
                                 if line.startswith("|")))
                assert "|" in chunk.text, chunk.chunk_id
            total = ranges[0][2]
            assert ranges[0][0] == 1 and ranges[-1][1] == total, ranges
            assert all(later[0] == earlier[1] + 1
                       for earlier, later in zip(ranges, ranges[1:])), ranges
            assert len(headers) == 1, f"{doc} p{page} t{number}: header row changed"
    assert splits >= 1, "no split table found, so the row-group rule is unproven"


def real_corpus_ids_unique_and_ordered():
    for doc, pages in _corpus().items():
        chunks = build.chunks_for_document(pages, DocMeta(file=doc))
        ids = [chunk.chunk_id for chunk in chunks]
        assert len(set(ids)) == len(ids), f"{doc}: duplicate chunk ids"
        pages_seen = [chunk.page_start for chunk in chunks]
        assert pages_seen == sorted(pages_seen), f"{doc}: chunks not in page order"


def _doc(fragment: str):
    for doc, pages in _corpus().items():
        if fragment in doc:
            return doc, pages
    raise AssertionError(f"no corpus document matching {fragment!r}")


def _table_chunks(doc: str, pages: list) -> list:
    return [chunk for chunk in build.chunks_for_document(pages, DocMeta(file=doc, year=1970))
            if chunk.type == "table"]


def real_corpus_caption_below_siwakoti_p4():
    """0_Siwakoti p4 prints `Table 2 – Area, production...` *under* the table."""
    doc, pages = _doc("0_Siwakoti")
    captions = [chunk.caption for chunk in _table_chunks(doc, pages) if chunk.page_start == 4]
    assert any("Area, production, and yield of cucumber" in cap for cap in captions), captions


def real_corpus_caption_below_ali_p2():
    """1970_Ali p2 prints `Table 1. Trace Nutrient Concentrations` under the table."""
    doc, pages = _doc("1970_Ali_Treatment")
    captions = [chunk.caption for chunk in _table_chunks(doc, pages) if chunk.page_start == 2]
    assert any("Trace Nutrient Concentrations" in cap for cap in captions), captions


def real_corpus_caption_table_no_style():
    """1970_Acharya writes `Table No. 2: HDI of rural and urban region 1990 and 2000`."""
    doc, pages = _doc("1970_Acharya_Dimension")
    captions = [chunk.caption for chunk in _table_chunks(doc, pages)]
    assert any("Table No. 2: HDI" in cap for cap in captions), captions


def real_corpus_caption_coverage_does_not_drop():
    """37 of 268 table chunks carried a caption on 2026-11-15; never go below that."""
    captioned = total = 0
    for doc, pages in _corpus().items():
        for chunk in _table_chunks(doc, pages):
            total += 1
            captioned += 1 if chunk.caption else 0
    assert captioned >= 37, f"captions fell to {captioned} of {total} table chunks"


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
                     ("a caption printed below the table is used",
                      caption_below_the_table),
                     ("Table No. 2 style is recognised", caption_style_table_no),
                     ("a far caption is used only when nothing sits between",
                      far_caption_only_when_nothing_between),
                     ("units are collected from several header cells",
                      units_collects_several_columns),
                     ("parentheticals that are not units are ignored",
                      units_ignore_non_units),
                     ("a note 80 pt below is still kept", note_further_below_is_kept),
                     ("short prose is not a table note", short_prose_is_not_a_note),
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
                     ("real corpus: every detected table is rendered",
                      real_corpus_has_every_detected_table),
                     ("real corpus: split tables repeat the header and tile the rows",
                      real_corpus_split_tables_repeat_the_header),
                     ("real corpus: ids unique and in page order",
                      real_corpus_ids_unique_and_ordered)]:
        check(name, fn)

    print("real corpus: the captions that were hard to reach")
    for name, fn in [("a caption printed below the table (Siwakoti p4)",
                      real_corpus_caption_below_siwakoti_p4),
                     ("a caption printed below the table (Ali p2)",
                      real_corpus_caption_below_ali_p2),
                     ("`Table No. 2:` numbering (Acharya)",
                      real_corpus_caption_table_no_style),
                     ("caption coverage never drops below 37 of 268",
                      real_corpus_caption_coverage_does_not_drop)]:
        check(name, fn)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
