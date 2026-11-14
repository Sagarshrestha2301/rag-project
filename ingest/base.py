"""Shared shapes and the parser registry for Step 3.

Every parser returns `PageResult` so Steps 4-6 never care which tier produced a
page, and adding Docling later is one module plus one `register()` call.

Usage:
    from ingest import base
    @base.register("pymupdf4llm")
    class TextParser: ...
    base.get("pymupdf4llm")
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Table:
    """One table on one page, cells exactly as they appear in the PDF."""

    rows: list[list[str]]
    bbox: tuple[float, float, float, float]
    parser: str                       # which tier assembled the cells
    headers_from: str = "cells"       # "cells" | "none"
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"rows": self.rows, "bbox": list(self.bbox), "parser": self.parser,
                "headers_from": self.headers_from, "notes": self.notes}


@dataclass
class PageResult:
    doc: str                # file name inside data/corpus/
    pdf_page: int           # 1-based PDF index; eval gold_sources use this
    text: str               # plain text for embedding / BM25 (flattened)
    parser: str
    chars: int = 0
    ocr: bool = False
    printed_label: str = ""  # number as printed on the page, "" when not found
    # Line-preserving blocks, in reading order, for Step 4's chunker. `text` is a
    # single flattened string and cannot express headings or paragraphs; this can.
    # Empty on OCR pages, where no line structure exists to preserve.
    blocks: list[str] = field(default_factory=list)
    # One (x0, y0, x1, y1) per entry in `blocks`, same order. Step 4 needs the
    # geometry to drop table blocks from text chunks, so no table is embedded
    # twice; without it the bbox in tables.jsonl cannot be matched to a block.
    block_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.chars:
            self.chars = len(self.text)

    def as_dict(self) -> dict:
        return {"doc": self.doc, "pdf_page": self.pdf_page, "chars": self.chars,
                "parser": self.parser, "ocr": self.ocr,
                "printed_label": self.printed_label,
                "text": self.text,
                "blocks": self.blocks,
                "block_rects": [list(rect) for rect in self.block_rects],
                "tables": [t.as_dict() for t in self.tables],
                "notes": self.notes}


class Parser(Protocol):
    name: str

    def handles(self, page) -> bool: ...
    def parse(self, page, *, doc: str, pdf_page: int) -> PageResult: ...


REGISTRY: dict[str, type] = {}


def register(name: str):
    """Class decorator: register a parser under `name`."""

    def wrap(cls):
        cls.name = name
        REGISTRY[name] = cls
        return cls

    return wrap


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"unknown parser {name!r}; registered: {sorted(REGISTRY)}")
    return REGISTRY[name]


def corpus_files(corpus: pathlib.Path = pathlib.Path("data/corpus")) -> list[pathlib.Path]:
    """Every corpus PDF, recursively: new documents keep their source folder.

    D-030 mirrors `data/raw`'s relative folders inside `data/corpus`, so a flat
    glob would silently ignore everything the Drive sample added.

    Page, table and citation records identify a document by its file name, so two
    documents with the same name would be indistinguishable downstream. That is
    a corpus mistake, not something to paper over at read time.
    """
    files = sorted(corpus.rglob("*.pdf"))
    seen: dict[str, pathlib.Path] = {}
    for path in files:
        if path.name in seen:
            raise RuntimeError(
                f"duplicate corpus file name {path.name!r}: {seen[path.name]} and {path}"
            )
        seen[path.name] = path
    return files


def corpus_path(doc: str, corpus: pathlib.Path = pathlib.Path("data/corpus")) -> pathlib.Path:
    """The file behind a name recorded in `PageResult.doc`."""
    matches = [p for p in corpus.rglob(doc)]
    if not matches:
        raise FileNotFoundError(f"no corpus file named {doc!r} under {corpus}")
    if len(matches) > 1:
        raise RuntimeError(f"corpus file name {doc!r} is ambiguous: {[str(m) for m in matches]}")
    return matches[0]
