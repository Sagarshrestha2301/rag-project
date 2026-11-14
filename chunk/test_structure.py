"""Prove the heading rule against this corpus's real shapes and traps.

Every case here came out of the parsed output, not from imagination: the two
heading shapes, the three trap families (decimal cells, affiliation lines,
sentence-glued list numbers) and the headingless documents.

The last two cases matter most, because they are the definition-of-done's
"no chunk crosses a heading" check: one proves the guard accepts a chunk built
from a single section, and the other proves the guard *fires* when two sections
are spliced into one chunk. A check that cannot fail proves nothing.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_structure.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import structure                      # noqa: E402
from chunk.base import Block                     # noqa: E402

PARSED = pathlib.Path("index/parsed/pages.jsonl")
FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def expect_error(name: str, fn) -> None:
    try:
        fn()
    except ValueError:
        print(f"  PASS  {name}")
        return
    FAILURES.append(name)
    print(f"  FAIL  {name}: no ValueError raised")


def block(text: str, page: int = 3) -> Block:
    return Block(pdf_page=page, text=text, index=0)


# --- heading shapes -------------------------------------------------------

def shape_a():
    assert structure.parse_heading(block("1. BACKGROUND")) == ("1", "BACKGROUND")


def shape_b_wrapped():
    got = structure.parse_heading(block(
        "3.5\nSpatial distribution of\nstandard deviation and\n"
        "coefficient of variance of\nsummer monsoon rainfall"))
    assert got == ("3.5", "Spatial distribution of standard deviation and "
                          "coefficient of variance of summer monsoon rainfall"), got


def shape_b_short():
    assert structure.parse_heading(block("2.\nDATA USED AND METHODOLOGY")) == (
        "2", "DATA USED AND METHODOLOGY")


# --- traps ----------------------------------------------------------------

def decimal_cells_rejected():
    for text in ("21.84\n31.67", "0.48\n0.48", "54.27\n50.00", "1.44\n19. Plants die"):
        assert structure.parse_heading(block(text, page=9)) is None, text


def affiliation_rejected():
    line = "1 SAARC Meteorological Research Centre (SMRC), Agargaon, Dhaka, Bangladesh"
    assert structure.parse_heading(block(line, page=1)) is None


def sentence_glued_number_rejected():
    text = ("19. Plants die after flowering and are inauspicious for the family "
            "which planted it so people avoid them")
    assert structure.parse_heading(block(text)) is None


def terminal_period_rejected():
    assert structure.parse_heading(block("3. RESULTS.")) is None


def glyph_only_title_rejected():
    assert structure.parse_heading(block("5.\n\uf8fa\uf8fb", page=4)) is None


# --- sections -------------------------------------------------------------

def hierarchy_path():
    pages = [_page(1, ["3.\nRESULTS AND DISCUSSION", "body one",
                       "3.1\nOnset and Withdrawal", "body two"])]
    sections = structure.split_sections(pages)
    assert [s.path for s in sections] == [
        ["3. RESULTS AND DISCUSSION"],
        ["3. RESULTS AND DISCUSSION", "3.1 Onset and Withdrawal"],
    ], [s.path for s in sections]
    # A subsection number must not end up with two dots ("3.1. Onset").
    assert sections[1].label == "3.1 Onset and Withdrawal", sections[1].label


def headingless_doc_is_per_page():
    pages = [_page(1, ["no heading here", "still none"]),
             _page(2, ["nor here"])]
    sections = structure.split_sections(pages)
    assert [(s.source, s.page_start, s.page_end) for s in sections] == [
        ("none", 1, 1), ("none", 2, 2)], [(s.source, s.page_start) for s in sections]
    assert all(s.path == [] for s in sections)


def ocr_page_kept_as_one_block():
    # OCR pages have no blocks, only text. Dropping them would lose 4 of 42 pages.
    pages = [_page(1, [], text="scanned text here"), _page(2, [], text="more scan")]
    blocks = structure.document_blocks(pages)
    assert [b.pdf_page for b in blocks] == [1, 2], blocks
    sections = structure.split_sections(pages)
    assert [(s.source, s.page_start) for s in sections] == [("none", 1), ("none", 2)]


def heading_section_spans_pages():
    pages = [_page(1, ["2. STUDY AREA", "text on one"]),
             _page(2, ["text on two", "3. RAINFALL DATA", "more"])]
    sections = structure.split_sections(pages)
    assert (sections[0].page_start, sections[0].page_end) == (1, 2), sections[0]
    assert sections[1].page_start == 2


def _page(number: int, blocks: list[str], text: str = ""):
    """A stand-in for an ingest PageResult, which only needs page + blocks."""

    class Page:
        pdf_page = number

    Page.blocks = blocks
    Page.text = text
    return Page


# --- the no-cross-section guard ------------------------------------------

def guard_accepts_one_section():
    pages = [_page(1, ["1. BACKGROUND", "alpha", "beta"])]
    sections = structure.split_sections(pages)
    structure.assert_no_cross_section(sections[0].blocks, sections)


def guard_fires_on_mixed_chunk():
    pages = [_page(1, ["1. BACKGROUND", "alpha", "2. STUDY AREA", "beta"])]
    sections = structure.split_sections(pages)
    mixed = sections[0].blocks + sections[1].blocks
    expect_error("guard fires when a chunk spans two sections",
                 lambda: structure.assert_no_cross_section(mixed, sections))


# --- the real corpus ------------------------------------------------------

def _corpus() -> dict[str, list]:
    if not PARSED.exists():
        raise AssertionError(f"{PARSED} missing: run `python -m ingest.cli build`")

    class Page:
        def __init__(self, number, blocks, text):
            self.pdf_page = number
            self.blocks = blocks
            self.text = text

    docs: dict[str, list] = {}
    for line in PARSED.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        docs.setdefault(record["doc"], []).append(
            Page(record["pdf_page"], record["blocks"], record["text"]))
    for pages in docs.values():
        pages.sort(key=lambda page: page.pdf_page)
    return docs


def real_corpus_every_block_once():
    for doc, pages in _corpus().items():
        blocks = structure.document_blocks(pages)
        sections = structure.split_sections(pages)
        placed = [b.index for section in sections for b in section.blocks]
        # Heading blocks become section metadata, so the body blocks are what
        # must survive into sections, once each and in reading order.
        expected = [b.index for b in blocks if structure.parse_heading(b, 1) is None]
        assert placed == expected, (
            f"{doc}: {len(placed)} placed of {len(expected)} body blocks, or out of order")
        for section in sections:
            structure.assert_no_cross_section(section.blocks, sections)
        if len(blocks) > 3:
            assert sections, f"{doc}: no sections"


def real_corpus_headings_found():
    docs = _corpus()
    found = {doc[:22]: sum(1 for s in structure.split_sections(pages)
                           if s.source == "heading")
             for doc, pages in docs.items()}
    for prefix, expected in (("1970_Marahatta", 5), ("1970_Ahasan", 14),
                             ("1970_Das_Beliefs", 0), ("1976_Watanabe", 0),
                             ("0_NARAYAN", 0)):
        match = [value for name, value in found.items() if name.startswith(prefix)]
        assert match, f"{prefix}: no such document in {sorted(found)}"
        assert match[0] == expected, f"{prefix}: {match[0]} headings, expected {expected}"

    # The scan has no blocks at all; its text fallback must still yield its pages.
    narayan = [pages for doc, pages in docs.items() if doc.startswith("0_NARAYAN")][0]
    scan_sections = structure.split_sections(narayan)
    assert len(scan_sections) == len(narayan), (
        f"scan: {len(scan_sections)} sections for {len(narayan)} pages")


def main() -> int:
    print("heading shapes")
    for name, fn in [("shape A: number + title on one line", shape_a),
                     ("shape B: number alone, title wrapped", shape_b_wrapped),
                     ("shape B: number alone, short title", shape_b_short),
                     ("hierarchy: subsection carries its parent", hierarchy_path),
                     ("section spans pages until the next heading", heading_section_spans_pages),
                     ("OCR page (no blocks) is kept as one block", ocr_page_kept_as_one_block),
                     ("headingless document falls back to page sections", headingless_doc_is_per_page)]:
        check(name, fn)

    print("traps (each must be rejected)")
    for name, fn in [("decimal table cells", decimal_cells_rejected),
                     ("affiliation lines on page 1", affiliation_rejected),
                     ("sentence glued to a list number", sentence_glued_number_rejected),
                     ("title with a terminal period", terminal_period_rejected),
                     ("glyph-only title", glyph_only_title_rejected)]:
        check(name, fn)

    print("no chunk crosses a heading")
    check("guard accepts a single-section chunk", guard_accepts_one_section)
    guard_fires_on_mixed_chunk()

    print("real corpus")
    check("every block lands in exactly one section, in order", real_corpus_every_block_once)
    check("heading counts match the measured corpus", real_corpus_headings_found)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
