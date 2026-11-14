"""OCR tier for pages with no text layer (the NARAYAN scan).

Uses the pinned parser's OCR (`pymupdf4llm` + RapidOCR) rather than a second OCR
stack, so the text here matches what the UI index already produces. OCR runs per
document, because the library's OCR pass is document-scoped; the caller only
pays for it when at least one page is empty.

Usage:
    from ingest.ocr import ocr_pages
    ocr_pages(path)   # {1: "text of page 1", ...}
"""

from __future__ import annotations

import pathlib
import re

OCR_DPI = 200


def ocr_pages(path: pathlib.Path) -> dict[int, str]:
    """{1-based page number: text} for a document, or {} if OCR is unavailable."""
    import pymupdf4llm

    try:
        chunks = pymupdf4llm.to_markdown(
            str(path), page_chunks=True, use_ocr=True, ocr_dpi=OCR_DPI
        )
    except Exception as exc:  # noqa: BLE001 - OCR failure must not stop the run
        print(f"[ingest.ocr] OCR failed for {path.name}: {exc.__class__.__name__}: {exc}")
        return {}

    out: dict[int, str] = {}
    for position, chunk in enumerate(chunks):
        # pymupdf4llm 2.1 returns one chunk per page in page order and leaves
        # metadata["page"] unset, so position is the page number.
        page = (chunk.get("metadata") or {}).get("page")
        number = (int(page) + 1) if page is not None else position + 1
        text = re.sub(r"[|#*_`]+", " ", chunk.get("text") or "")
        out[number] = re.sub(r"\s+", " ", text).strip()
    return out
