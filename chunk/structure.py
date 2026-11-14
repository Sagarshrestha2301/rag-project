"""Headings and sections, built from the shapes this corpus actually has.

Two heading shapes were measured on the parsed blocks, and both are real:

* **Shape A**, number and title on one line: `1. BACKGROUND` (Marahatta).
* **Shape B**, the number alone with the title beneath it, sometimes wrapped
  over several lines: a block whose first line is `3.5` and whose remaining
  lines read `Spatial distribution of / standard deviation and / ...` (Ahasan).

The traps are measured too, not hypothetical:

* decimal table cells look exactly like a number: `21.84`, `0.48`, `54.27`
  (19 blocks in this corpus). Rejected by allowing only single-digit parts
  after the first, so `3.9` is a subsection and `21.84` is not.
* Ahasan page 1 has three affiliation lines that read like headings:
  `1 SAARC Meteorological Research Centre (SMRC), Agargaon, Dhaka, Bangladesh`.
  Rejected by the page-1 comma/parenthesis rule.
* Das page 3 has `19. Plants die after flowering ...` — a real integer with a
  sentence glued to it. Rejected by the word cap.
* Capitalisation is never a signal: the PDF damages it (`INtrODUCtION`,
  `DAtA USED AND MEtHODOLOGY`).

OCR pages carry no blocks, only flattened text, so they are kept as one block
per page. Without that, the scan's four pages produce zero sections and leave
the chunker silently.

Usage:
    from chunk import structure
    sections = structure.split_sections(pages)
    sections[0].path          # ['1. INTRODUCTION']
    sections[1].page_start    # 2
    structure.assert_no_cross_section(my_chunk_blocks, sections)
"""

from __future__ import annotations

import re

from chunk.base import Block, Section

HEADING_MAX_WORDS = 15     # the longest real heading here is 14 words (Ahasan 3.5)
HEADING_MIN_LETTERS = 2    # rejects glyph-only titles like "\uf8fa\uf8fb"

# 1-2 digits, then optional single-digit parts: "3.1" yes, "21.84" no.
_HEADING = re.compile(r"^(\d{1,2}(?:\.\d)*)\.?(?:\s+(.*))?$")


def document_blocks(pages) -> list[Block]:
    """Every block of a document in reading order, with a document-wide index.

    Usage:
        from chunk.structure import document_blocks
        len(document_blocks(pages))   # 188 for Das
    """
    blocks: list[Block] = []
    for page in pages:
        texts = [text for text in page.blocks if text.strip()]
        had_blocks = bool(texts)
        if not texts and getattr(page, "text", "").strip():
            # OCR pages have no line structure at all: `blocks` is empty by
            # design. Keeping their flattened text as one block stops four pages
            # of this corpus (the whole NARAYAN scan) from silently disappearing
            # from chunking, which is the D-020 problem coming back one step later.
            texts = [page.text.strip()]
        for position, text in enumerate(texts):
            blocks.append(Block(pdf_page=page.pdf_page, text=text,
                                index=len(blocks),
                                page_block=position if had_blocks else -1))
    return blocks


def parse_heading(block: Block, first_page: int = 1) -> tuple[str, str] | None:
    """Return `(number, title)` when the block is a heading, else None.

    Usage:
        parse_heading(Block(3, "2.\\nDATA USED AND METHODOLOGY", 0))   # ('2', 'DATA USED AND METHODOLOGY')
        parse_heading(Block(9, "21.84\\n31.67", 4))                    # None
    """
    lines = [line.strip() for line in block.text.splitlines() if line.strip()]
    if not lines:
        return None

    match = _HEADING.match(lines[0])
    if not match:
        return None
    number, head = match.group(1), (match.group(2) or "").strip()
    if any(len(part) > 1 for part in number.split(".")[1:]):
        return None                     # 21.84 and 0.48 are cells, not sections

    title = " ".join([head, *lines[1:]]).strip()
    if not title or title.endswith(".") or len(title.split()) > HEADING_MAX_WORDS:
        return None

    letters = sum(1 for char in title if char.isascii() and char.isalpha())
    if letters < HEADING_MIN_LETTERS or letters / len(title) < 0.3:
        return None                     # a glyph run is a figure label, not a title

    if block.pdf_page == first_page and ("," in title or "(" in title):
        return None                     # affiliation line, e.g. "1 SAARC ... (SMRC), Agargaon, Dhaka"
    return number, title


def split_sections(pages) -> list[Section]:
    """Group a document's blocks into sections, one heading deep.

    A section runs until the next heading, so it may span pages. Documents with
    no headings at all (Das, Watanabe) get one section per page, labelled
    `source="none"`, so their page ranges stay trustworthy.

    Usage:
        from chunk.structure import split_sections
        [s.label for s in split_sections(marahatta_pages)]
        # ['1. BACKGROUND', '2. STUDY AREA', '3. RAINFALL DATA', ...]
    """
    blocks = document_blocks(pages)
    first_page = min((page.pdf_page for page in pages), default=1)
    sections: list[Section] = []
    current: Section | None = None
    stack: list[tuple[int, str]] = []    # (depth, label) of the open headings

    for block in blocks:
        parsed = parse_heading(block, first_page)
        if parsed:
            number, title = parsed
            depth = len(number.split("."))
            stack = [item for item in stack if item[0] < depth]
            # "3. RESULTS..." for a top level, "3.1 Onset..." for a subsection:
            # a number that already contains a dot must not get a second one.
            label = f"{number}. {title}" if "." not in number else f"{number} {title}"
            stack.append((depth, label))
            current = Section(number=number, title=title,
                              path=[label for _, label in stack],
                              source="heading", heading_page=block.pdf_page)
            sections.append(current)
            continue

        if current is None or (current.source == "none"
                               and current.page_start != block.pdf_page):
            current = Section(number="", title="", path=[], source="none",
                              heading_page=block.pdf_page)
            sections.append(current)
        current.blocks.append(block)

    # A heading whose body is a table or a figure has no blocks; it still exists.
    return [section for section in sections
            if section.blocks or section.source == "heading"]


def section_lookup(sections: list[Section]) -> dict[int, int]:
    """{block index: section position}, for the cross-section check."""
    return {block.index: position
            for position, section in enumerate(sections)
            for block in section.blocks}


def assert_no_cross_section(blocks, sections: list[Section]) -> None:
    """Raise if a chunk's blocks come from more than one section.

    This is the guard behind the definition of done's "no chunk crosses a
    heading". It takes the blocks a chunk was built from, not its text, so it
    cannot be fooled by a heading word appearing inside a sentence.

    Usage:
        from chunk.structure import assert_no_cross_section
        assert_no_cross_section(chunk_blocks, sections)   # raises ValueError
    """
    lookup = section_lookup(sections)
    found = {lookup[block.index] for block in blocks if block.index in lookup}
    if len(found) > 1:
        labels = sorted(sections[position].label or "(page section)" for position in found)
        raise ValueError(f"chunk spans {len(found)} sections: {labels}")
    missing = [block.index for block in blocks if block.index not in lookup]
    if missing:
        raise ValueError(f"blocks not in any section: {missing[:5]}")
