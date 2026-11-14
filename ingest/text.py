"""Tier 1: plain text pages through the pinned parser (D-005).

One page in, one `PageResult` out. `pymupdf4llm` is asked per page so a table
page can be handed to the table tier without re-parsing the whole document.

Two text fields come back on purpose: `text` is flattened for BM25, `blocks`
keeps the block and line structure Step 4's chunker needs to find headings.

Usage:
    from ingest.text import TextParser
    TextParser().parse(page, doc="x.pdf", pdf_page=3)
"""

from __future__ import annotations

import re

import pymupdf4llm

from ingest import base


@base.register("pymupdf4llm")
class TextParser:
    """Text pages. Never OCRs: that is `ingest.ocr`."""

    name = "pymupdf4llm"

    def handles(self, page) -> bool:
        return True

    def parse(self, page, *, doc: str, pdf_page: int) -> base.PageResult:
        text = _page_markdown(page)
        geometry = block_geometry(page)
        return base.PageResult(doc=doc, pdf_page=pdf_page, text=text,
                               parser=self.name, printed_label=printed_label(page),
                               blocks=[block for block, _ in geometry],
                               block_rects=[rect for _, rect in geometry])


def page_blocks(page) -> list[str]:
    """Line-preserving text blocks in reading order, for chunking.

    `PageResult.text` is flattened to one line for BM25, which erases headings
    and paragraphs. This keeps one string per block, lines inside a block intact.

    Usage:
        from ingest.text import page_blocks
        page_blocks(page)[:2]
        # ['December 2010', 'M. N. Ahasan, Md. A.M. Chowdhary & D. A. Quadir']
    """
    return [block for block, _ in block_geometry(page)]


def block_geometry(page) -> list[tuple[str, tuple[float, float, float, float]]]:
    """(text, (x0, y0, x1, y1)) per text block, in reading order.

    Step 4 uses the rectangles to tell which blocks sit inside a table's bbox.

    Usage:
        from ingest.text import block_geometry
        block_geometry(page)[0]
        # ('December 2010', (36.0, 30.1, 240.2, 41.5))
    """
    found: list[tuple[float, float, str, tuple[float, float, float, float]]] = []
    for block in page.get_text("blocks"):
        x0, y0, x1, y1, raw = block[0], block[1], block[2], block[3], block[4]
        kind = block[6] if len(block) > 6 else 0
        if kind != 0:                      # 1 is an image block: no text to keep
            continue
        lines = [re.sub(r"\s+", " ", line).strip()
                 for line in (raw or "").splitlines()]
        kept = [line for line in lines if line]
        if kept:
            rect = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
            found.append((round(y0, 1), round(x0, 1), "\n".join(kept), rect))
    found.sort(key=lambda item: (item[0], item[1]))
    return [(text, rect) for _, _, text, rect in found]


def strip_furniture(pages, share: float = 0.6, longest: int = 200) -> int:
    """Remove running headers/footers from `blocks`; never touches `text`.

    Matching is per *line*, not per block: a header's lines are grouped into a
    different block on each page, so block-level comparison misses them (measured:
    Ahasan's header survived on every page that way). Digits are normalised first,
    because the header carries the page number and so differs page to page.

    Only the first and last block of a page can *become* furniture, because that is
    where headers and footers live. Matching against every line instead cost
    Watanabe 201 lines on 7 pages: repeated figure axis labels mid-page look like
    furniture by frequency alone.

    Usage:
        from ingest.text import strip_furniture
        strip_furniture(pages)   # 25 header/footer lines removed
    """
    if len(pages) < 3:                     # too few pages to call anything a repeat
        return 0

    seen: dict[str, set[int]] = {}
    for page in pages:
        edges = page.blocks[:1] + page.blocks[-1:] if page.blocks else []
        lines = {line for block in edges for line in block.splitlines()}
        for line in lines:
            if len(line) <= longest:
                seen.setdefault(_signature(line), set()).add(page.pdf_page)

    limit = max(2, int(share * len(pages)))
    repeated = {sig for sig, pages_seen in seen.items() if len(pages_seen) >= limit}
    if not repeated:
        return 0

    removed = 0
    for page in pages:
        kept_blocks = []
        kept_rects = []
        for position, block in enumerate(page.blocks):
            lines = block.splitlines()
            surviving = [line for line in lines if _signature(line) not in repeated]
            removed += len(lines) - len(surviving)
            kept = "\n".join(surviving).strip()
            if kept:
                kept_blocks.append(kept)
                # Keep rects index-aligned with blocks: a dropped block drops its
                # rectangle too, or Step 4 would match the wrong geometry.
                rects = getattr(page, "block_rects", [])
                if position < len(rects):
                    kept_rects.append(rects[position])
        page.blocks = kept_blocks
        if getattr(page, "block_rects", []):
            page.block_rects = kept_rects
    return removed


def _signature(line: str) -> str:
    """A line's identity with page numbers blanked out."""
    return re.sub(r"\d+", "#", line.lower()).strip()


def _page_markdown(page) -> str:
    """Markdown for a single page, whitespace-normalised to plain text."""
    try:
        chunks = pymupdf4llm.to_markdown(
            page.parent.name, pages=[page.number], page_chunks=True, use_ocr=False
        )
        raw = chunks[0].get("text", "") if chunks else ""
    except Exception:  # noqa: BLE001 - fall back to the raw text layer
        raw = page.get_text()
    return normalise(raw)


def normalise(text: str) -> str:
    """Markdown leftovers out, readable text in."""
    text = re.sub(r"[|#*_`]+", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def printed_label(page) -> str:
    """The page number as printed on the page, or "" when none is found.

    Only recorded, never used to renumber: gold pages refer to the PDF index.
    """
    lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
    for line in lines[:2] + lines[-2:]:
        match = re.match(r"^(\d{1,4})(?:\s|$)", line)
        if not match:
            continue
        value = int(match.group(1))
        # A four-digit "page number" near 1900-2030 is a year in the header, not a page.
        if len(match.group(1)) == 4 and 1900 <= value <= 2030:
            continue
        return match.group(1)
    return ""
