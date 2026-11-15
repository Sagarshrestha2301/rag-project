"""Prove the review sheet picks the promised sample and escapes what it shows.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_review.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import review                     # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def _chunk(index: int, kind: str = "text", text: str | None = None) -> dict:
    return {
        "chunk_id": f"doc{index}:p1-1:0000",
        "file": f"doc{index}.pdf",
        "page_start": 1, "page_end": 1,
        "section_path": ["1. BACKGROUND"],
        "section_path_source": "heading",
        "text": text if text is not None else f"body {index}",
        "type": kind,
        "block_indices": [0],
        "caption": "Table 1: Rainfall" if kind == "table" else "",
        "units": "mm" if kind == "table" else "",
        "footnotes": ["Source: SMRC"] if kind == "table" else [],
        "notes": [],
        "year": 1970, "publisher": "SMRC", "doc_type": "report",
        "doc_context": "A two-line context.",
        "ocr": False,
        "chunker_version": "step4-v1",
    }


def sample_is_deterministic_and_has_three_tables():
    chunks = [_chunk(i, "table" if i < 4 else "text") for i in range(20)]
    first = review.sample(chunks, seed=7)
    second = review.sample(chunks, seed=7)
    assert len(first) == 10, len(first)
    assert sum(1 for c in first if c["type"] == "table") == 3, first
    assert [c["chunk_id"] for c in first] == [c["chunk_id"] for c in second]


def sample_spreads_across_documents():
    chunks = [_chunk(i, "table" if i < 4 else "text") for i in range(20)]
    picked = review.sample(chunks, seed=3)
    assert len({c["file"] for c in picked}) == 10, [c["file"] for c in picked]


def a_small_corpus_reuses_documents_rather_than_returning_fewer_chunks():
    chunks = []
    for doc in range(4):
        for position in range(3):
            kind = "table" if position == 0 and doc < 3 else "text"
            chunk = _chunk(doc * 3 + position, kind)
            chunk["file"] = f"doc{doc}.pdf"
            chunk["chunk_id"] = f"doc{doc}:p1-{position}:0000"
            chunks.append(chunk)
    picked = review.sample(chunks, seed=3)
    assert len(picked) == 10, len(picked)
    assert len({c["file"] for c in picked}) == 4, picked


def too_few_tables_is_an_error_not_a_silent_text_sample():
    chunks = [_chunk(i, "table" if i < 2 else "text") for i in range(10)]
    try:
        review.sample(chunks, seed=1)
    except ValueError as exc:
        assert "table chunks" in str(exc), exc
    else:
        raise AssertionError("asking for 3 tables from 2 must fail")


def html_escapes_text_and_shows_table_fields():
    chunk = _chunk(1, "table", text="<script>alert(1)</script> & more")
    chunk["caption"] = "A & B"
    out = pathlib.Path(tempfile.mkdtemp()) / "review.html"
    review.write_html([chunk], out)
    page = out.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in page, page[:400]
    assert "<script>" not in page, page[:400]
    assert "A &amp; B" in page, page[:400]
    assert "caption" in page and "units" in page and "footnotes" in page


def main() -> int:
    print("sample")
    for name, fn in [
        ("deterministic, three of ten are tables", sample_is_deterministic_and_has_three_tables),
        ("one chunk per document when possible", sample_spreads_across_documents),
        ("a small corpus reuses documents", a_small_corpus_reuses_documents_rather_than_returning_fewer_chunks),
        ("too few tables fails loudly", too_few_tables_is_an_error_not_a_silent_text_sample),
    ]:
        check(name, fn)

    print("sheet")
    check("text is escaped and table fields are shown", html_escapes_text_and_shows_table_fields)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
