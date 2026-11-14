"""Build the parsed corpus: pages, tables and a per-document manifest.

Outputs (all regenerable, none committed):
    index/parsed/pages.jsonl    one PageResult per line (text + line-preserving blocks)
    index/parsed/tables.jsonl   one table per line, with its parser
    index/parsed/manifest.json  per-document summary + timings

Usage:
    .venv\\Scripts\\python.exe -m ingest.cli build
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import time

import pdfplumber
import pymupdf

from ingest import ocr, tables, text
from ingest.base import PageResult, corpus_files

MIN_TEXT_CHARS = 40      # below this a page is treated as having no text layer


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_document(path: pathlib.Path) -> tuple[list[PageResult], dict]:
    """Every page of one PDF, each through the tier that fits it."""
    started = time.perf_counter()
    pages: list[PageResult] = []
    per_tier = {"pymupdf4llm": 0, "pymupdf-grid+words": 0, "rapidocr": 0}
    ocr_text: dict[int, str] | None = None
    table_seconds = 0.0

    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - one broken file must not stop a 60-doc build
        return [], _failed_summary(path, started, f"pymupdf: {exc.__class__.__name__}: {exc}")

    if doc.page_count == 0:
        # A truncated PDF can open without raising and still contain no pages.
        doc.close()
        return [], _failed_summary(path, started, "pymupdf found 0 pages")

    # pdfplumber parses the whole document when opened and raises on a truncated
    # one (`PdfminerException: Unexpected EOF`). That must cost this document its
    # table tier, not the entire run: it aborted a 60-document build at file 11.
    try:
        plumber_doc = pdfplumber.open(str(path))
    except Exception as exc:  # noqa: BLE001
        plumber_doc = None
        print(f"  ! {path.name[:40]}: pdfplumber could not open ({exc.__class__.__name__}); tables skipped")

    plumber_ctx = plumber_doc if plumber_doc is not None else _NullPlumber()
    with plumber_ctx as plumber, doc:
        for number, page in enumerate(doc, start=1):
            raw = page.get_text()
            if len(raw.strip()) < MIN_TEXT_CHARS:
                if ocr_text is None:
                    ocr_text = ocr.ocr_pages(path)
                said = ocr_text.get(number, "")
                if said:
                    pages.append(PageResult(
                        doc=path.name, pdf_page=number, text=said, parser="rapidocr",
                        ocr=True, printed_label="", notes=["no text layer; OCR used"],
                    ))
                    per_tier["rapidocr"] += 1
                    continue

            result = text.TextParser().parse(page, doc=path.name, pdf_page=number)
            began = time.perf_counter()
            found = tables.page_tables(
                pdf_page=page,
                pdfplumber_page=plumber.pages[number - 1] if number <= len(plumber.pages) else None,
            )
            table_seconds += time.perf_counter() - began
            if found:
                result.tables = found
                result.parser = "pymupdf-grid+words"
            per_tier[result.parser] += 1
            pages.append(result)

    summary = {
        "doc": path.name,
        "sha256": sha256(path),
        "pages": len(pages),
        "text_pages": sum(1 for p in pages if not p.ocr),
        "ocr_pages": sum(1 for p in pages if p.ocr),
        "table_pages": sorted(p.pdf_page for p in pages if p.tables),
        "tables": sum(len(p.tables) for p in pages),
        "unreadable_pages": [p.pdf_page for p in pages if p.chars < MIN_TEXT_CHARS],
        "parser_pages": per_tier,
        "printed_labels": {str(p.pdf_page): p.printed_label for p in pages if p.printed_label},
        "seconds": round(time.perf_counter() - started, 1),
        "table_seconds": round(table_seconds, 1),
        "errors": [] if plumber_doc is not None else ["pdfplumber could not open; tables skipped"],
    }
    return pages, summary


class _NullPlumber:
    """Stands in for a pdfplumber document that could not be opened."""

    pages: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


def _failed_summary(path: pathlib.Path, started: float, error: str) -> dict:
    """A document PyMuPDF cannot open at all: reported, not fatal."""
    print(f"  ! {path.name[:40]}: {error}")
    return {
        "doc": path.name, "sha256": sha256(path), "pages": 0, "text_pages": 0,
        "ocr_pages": 0, "table_pages": [], "tables": 0, "unreadable_pages": [],
        "parser_pages": {"pymupdf4llm": 0, "pymupdf-grid+words": 0, "rapidocr": 0},
        "printed_labels": {}, "seconds": round(time.perf_counter() - started, 1),
        "table_seconds": 0.0, "errors": [error],
    }


def build(out_dir: pathlib.Path = pathlib.Path("index/parsed"),
          pages_root: pathlib.Path = pathlib.Path("data/parsed")) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_root.mkdir(parents=True, exist_ok=True)
    all_pages: list[PageResult] = []
    docs: list[dict] = []
    started = time.perf_counter()

    for path in corpus_files():
        pages, summary = parse_document(path)
        # Document-scoped, because "repeats on most pages" needs every page.
        summary["furniture_lines"] = text.strip_furniture(pages)
        all_pages.extend(pages)
        docs.append(summary)
        print(f"  {path.name[:52]:54s} {summary['pages']:>2}p "
              f"tables={summary['tables']:>2} ocr={summary['ocr_pages']} "
              f"{summary['seconds']:>5.1f}s")

    with (out_dir / "pages.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for page in all_pages:
            fh.write(json.dumps(page.as_dict(), ensure_ascii=False) + "\n")

    # The step's expected output: one markdown file per page, with a header line.
    for page in all_pages:
        folder = pages_root / pathlib.Path(page.doc).stem
        folder.mkdir(parents=True, exist_ok=True)
        header = (f"file: data/corpus/{page.doc} | page: {page.pdf_page} | "
                  f"parser: {page.parser} | table: {'yes' if page.tables else 'no'}"
                  f"{' | ocr: yes' if page.ocr else ''}\n\n")
        (folder / f"page-{page.pdf_page:03d}.md").write_text(header + page.text + "\n",
                                                              encoding="utf-8")

    with (out_dir / "tables.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for page in all_pages:
            for index, table in enumerate(page.tables, start=1):
                fh.write(json.dumps({"doc": page.doc, "pdf_page": page.pdf_page,
                                     "table": index, **table.as_dict()},
                                    ensure_ascii=False) + "\n")

    manifest = {
        "corpus": "data/corpus",
        "docs": docs,
        "totals": {
            "documents": len(docs),
            "pages": len(all_pages),
            "tables": sum(len(p.tables) for p in all_pages),
            "ocr_pages": sum(1 for p in all_pages if p.ocr),
            "unreadable_pages": sum(len(d["unreadable_pages"]) for d in docs),
            "seconds": round(time.perf_counter() - started, 1),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
