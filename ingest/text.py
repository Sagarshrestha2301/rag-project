"""Tier 1: plain text pages through the pinned parser (D-005).

One page in, one `PageResult` out. `pymupdf4llm` is asked per page so a table
page can be handed to the table tier without re-parsing the whole document.

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
        return base.PageResult(doc=doc, pdf_page=pdf_page, text=text,
                               parser=self.name, printed_label=printed_label(page))


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
