"""Build the chunk index from parsed pages, one chunk record per line.

This is the only command that turns `index/parsed/pages.jsonl` into
`index/chunks.jsonl`. It gives every chunk the document metadata the path states
(year, publisher, document type) plus the optional 2-line document context, so
Step 5 can embed text without looking at file names.

The corpus name recorded in the parsed pages is a bare file name; the metadata
needs the corpus-relative path (`reports/USGS/...`). `corpus_paths()` joins the
two and refuses to guess when two documents share a name.

Usage:
    .venv\\Scripts\\python.exe -m chunk.cli build
    # index/chunks.jsonl, then:
    [json.loads(line) for line in open("index/chunks.jsonl")][:1]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import build, doc_context, meta         # noqa: E402
from chunk.base import DocMeta                     # noqa: E402
from corpus import files as corpus_files           # noqa: E402

PARSED = pathlib.Path("index/parsed/pages.jsonl")
CHUNKS = pathlib.Path("index/chunks.jsonl")


class ParsedPage:
    """The fields the chunkers use, from one `pages.jsonl` record."""

    def __init__(self, record: dict):
        self.pdf_page = record["pdf_page"]
        self.blocks = record["blocks"]
        self.block_rects = record.get("block_rects") or []
        self.tables = record.get("tables") or []
        self.text = record["text"]


def load_pages(parsed: pathlib.Path = PARSED) -> dict[str, list[ParsedPage]]:
    """Every document's pages, in page order."""
    if not parsed.exists():
        raise FileNotFoundError(f"{parsed} missing: run `python -m ingest.cli build` first")
    docs: dict[str, list[ParsedPage]] = {}
    for line in parsed.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            docs.setdefault(record["doc"], []).append(ParsedPage(record))
    for pages in docs.values():
        pages.sort(key=lambda page: page.pdf_page)
    return docs


def corpus_paths(root: pathlib.Path | None = None) -> dict[str, pathlib.Path]:
    """{bare file name: corpus path}, refusing duplicate names.

    `root` lets Step 8's ingestion pipeline chunk a temporary corpus copy without
    touching `data/corpus`; the default is the real one.
    """
    paths = corpus_files() if root is None else corpus_files(root)
    return {path.name: path for path in paths}


def document_meta(name: str, paths: dict[str, pathlib.Path],
                  contexts: dict[str, dict], first_page_text: str = "") -> DocMeta:
    """Path-derived metadata, then page-1 evidence for whatever the path lacks.

    The path is authoritative when it says something; the page is only asked when
    it does not. Page-1 text can add a year (volume or copyright line) or an outlet
    name that is printed there, and nothing else - see `chunk.meta`.
    """
    if name not in paths:
        raise FileNotFoundError(f"parsed document {name!r} is not in data/corpus")
    document = meta.to_meta(paths[name])
    if document.year is None:
        document.year = meta.year_from_text(first_page_text)
    if not document.publisher:
        document.publisher = meta.publisher_from_text(first_page_text)
    document.doc_context = contexts.get(name, {}).get("context", "")
    return document


def build_chunks(parsed: pathlib.Path = PARSED,
                 contexts: pathlib.Path = doc_context.CACHE,
                 root: pathlib.Path | None = None) -> list:
    """Every chunk of every document, metadata included, in document order."""
    paths = corpus_paths(root)
    known = doc_context.load(contexts)
    chunks = []
    for name, pages in sorted(load_pages(parsed).items()):
        document = document_meta(name, paths, known, pages[0].text if pages else "")
        chunks.extend(meta.apply(build.chunks_for_document(pages, document), document))
    return chunks


def check(chunks: list) -> list[str]:
    """Reasons the chunk index is not citable; empty means every chunk is."""
    problems = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk.file or not chunk.text.strip():
            problems.append(f"{chunk.chunk_id}: empty file or text")
        if not 1 <= chunk.page_start <= chunk.page_end:
            problems.append(f"{chunk.chunk_id}: bad pages {chunk.page_start}-{chunk.page_end}")
        if chunk.chunk_id in seen:
            problems.append(f"{chunk.chunk_id}: duplicate chunk id")
        seen.add(chunk.chunk_id)
        if chunk.type == "table" and not chunk.caption:
            # A table without its caption can still be cited, but says so instead
            # of pretending the caption was found.
            if "no caption found" not in " ".join(chunk.notes):
                problems.append(f"{chunk.chunk_id}: table has no caption and no note")
    return problems


def main() -> int:
    """`chunk.cli build`: write `index/chunks.jsonl`, and refuse to write a broken one."""
    parser = argparse.ArgumentParser(prog="chunk.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build", help="write index/chunks.jsonl")
    build_cmd.add_argument("--parsed", default=str(PARSED))
    build_cmd.add_argument("--contexts", default=str(doc_context.CACHE))
    build_cmd.add_argument("--out", default=str(CHUNKS))
    args = parser.parse_args()

    started = time.perf_counter()
    chunks = build_chunks(pathlib.Path(args.parsed), pathlib.Path(args.contexts))
    problems = check(chunks)
    if problems:
        raise SystemExit("chunk check failed:\n  " + "\n  ".join(problems[:20]))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk.as_dict(), ensure_ascii=False) + "\n")

    tables = sum(1 for chunk in chunks if chunk.type == "table")
    with_context = sum(1 for chunk in chunks if chunk.doc_context)
    print(f"{len(chunks)} chunks from {len({chunk.file for chunk in chunks})} documents "
          f"({tables} tables) in {time.perf_counter() - started:.1f}s")
    print(f"  with document context: {with_context}")
    print(f"  without a section path: {sum(1 for chunk in chunks if not chunk.section_path)}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
