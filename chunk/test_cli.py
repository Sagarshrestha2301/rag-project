"""Prove the chunk export refuses bad records and reads pages in order.

The real build needs the whole corpus, so these cases use a two-page temp file
and small `Chunk` stand-ins. They cover the checks that run on every build: a
duplicate id, a broken page range, a table that hides a missing caption.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_cli.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import cli                       # noqa: E402
from chunk.base import Chunk                # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def _chunk(**overrides) -> Chunk:
    fields = dict(chunk_id="a:p1-1:0000", file="a.pdf", page_start=1, page_end=1,
                  section_path=["1. BACKGROUND"], text="1. BACKGROUND\n\nalpha")
    fields.update(overrides)
    return Chunk(**fields)


# --- reading parsed pages -----------------------------------------------

def pages_are_grouped_and_in_page_order():
    parsed = pathlib.Path(tempfile.mkdtemp()) / "pages.jsonl"
    rows = [
        {"doc": "b.pdf", "pdf_page": 2, "blocks": ["second"], "text": "second",
         "block_rects": [[0, 0, 10, 10]], "tables": [{"bbox": [0, 0, 1, 1]}]},
        {"doc": "a.pdf", "pdf_page": 1, "blocks": ["first"], "text": "first"},
        {"doc": "b.pdf", "pdf_page": 1, "blocks": ["first"], "text": "first"},
    ]
    parsed.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    docs = cli.load_pages(parsed)
    assert sorted(docs) == ["a.pdf", "b.pdf"], sorted(docs)
    assert [page.pdf_page for page in docs["b.pdf"]] == [1, 2], docs["b.pdf"]
    # Block rectangles and detected tables decide which text becomes a table
    # chunk; dropping them here silently produced a corpus with no tables.
    second = docs["b.pdf"][1]
    assert len(second.block_rects) == 1 and len(second.tables) == 1, second.__dict__
    assert docs["a.pdf"][0].block_rects == [] and docs["a.pdf"][0].tables == []


def missing_parsed_file_says_what_to_run():
    missing = pathlib.Path(tempfile.mkdtemp()) / "pages.jsonl"
    try:
        cli.load_pages(missing)
    except FileNotFoundError as exc:
        assert "ingest.cli build" in str(exc), exc
    else:
        raise AssertionError("a missing pages.jsonl must not look like an empty corpus")


# --- the checks before writing ------------------------------------------

def good_chunks_pass():
    assert cli.check([_chunk(), _chunk(chunk_id="a:p2-2:0001", page_start=2,
                                       page_end=2, type="table",
                                       caption="Table 1: Rainfall",
                                       text="Table 1: Rainfall")]) == []


def a_duplicate_id_is_reported():
    problems = cli.check([_chunk(), _chunk()])
    assert any("duplicate chunk id" in problem for problem in problems), problems


def a_broken_page_range_is_reported():
    problems = cli.check([_chunk(page_start=3, page_end=2)])
    assert any("bad pages 3-2" in problem for problem in problems), problems


def a_captionless_table_must_say_so():
    silent = cli.check([_chunk(type="table", caption="", text="Table 1")])
    assert any("no caption" in problem for problem in silent), silent
    honest = cli.check([_chunk(type="table", caption="", text="Table 1",
                                notes=["no caption found above bbox"])])
    assert honest == [], honest


# --- metadata from the corpus path --------------------------------------

def document_meta_merges_the_cached_context():
    paths = {"1991_report.pdf": pathlib.Path("data/corpus/reports/USGS/1991_report.pdf")}
    got = cli.document_meta("1991_report.pdf", paths,
                            {"1991_report.pdf": {"context": "A report on floods."}})
    assert (got.year, got.publisher, got.doc_type) == (1991, "USGS", "report"), got
    assert got.doc_context == "A report on floods.", got


def an_unknown_document_is_not_silently_skipped():
    try:
        cli.document_meta("gone.pdf", {}, {})
    except FileNotFoundError as exc:
        assert "gone.pdf" in str(exc), exc
    else:
        raise AssertionError("a parsed document missing from the corpus must fail loudly")


def a_missing_context_is_an_empty_string():
    paths = {"a.pdf": pathlib.Path("data/corpus/a.pdf")}
    assert cli.document_meta("a.pdf", paths, {}).doc_context == ""


def main() -> int:
    print("parsed pages")
    for name, fn in [
        ("pages are grouped by document and in page order", pages_are_grouped_and_in_page_order),
        ("a missing pages.jsonl says what to run", missing_parsed_file_says_what_to_run),
    ]:
        check(name, fn)

    print("checks before writing")
    for name, fn in [
        ("good chunks pass", good_chunks_pass),
        ("a duplicate id is reported", a_duplicate_id_is_reported),
        ("a broken page range is reported", a_broken_page_range_is_reported),
        ("a captionless table must say so", a_captionless_table_must_say_so),
    ]:
        check(name, fn)

    print("metadata")
    for name, fn in [
        ("the cached context is merged in", document_meta_merges_the_cached_context),
        ("an unknown document fails loudly", an_unknown_document_is_not_silently_skipped),
        ("a missing context is an empty string", a_missing_context_is_an_empty_string),
    ]:
        check(name, fn)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
