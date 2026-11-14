"""Prove the text chunker's rules: size, overlap, prefix, and no cross-section.

The last group runs over the real corpus, which is the only place the rules meet
paragraphs nobody wrote for a test.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_text.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import structure, text                  # noqa: E402
from chunk.base import Block, DocMeta              # noqa: E402

PARSED = pathlib.Path("index/parsed/pages.jsonl")
FAILURES: list[str] = []
META = DocMeta(file="1970_Test_Paper_W1.pdf", year=1970,
               publisher="Banko Janakari, Vol. 15, No. 2", doc_type="journal-article")


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


class Page:
    def __init__(self, number: int, blocks: list[str], text: str = ""):
        self.pdf_page = number
        self.blocks = blocks
        self.text = text


def body(chunk) -> str:
    return chunk.text.split("\n\n", 1)[1]


def short_section() -> list:
    sentence = "Bamboo grows quickly. "
    return [Page(1, ["1. BACKGROUND", sentence * 3, sentence * 3])]


def long_section() -> list:
    paragraph = ("Summer monsoon rainfall varies across the country and the "
                 "variation matters for agriculture. ") * 8
    return [Page(1, ["1. BACKGROUND"])] + [Page(n, [paragraph]) for n in range(2, 8)]


# --- size and overlap ----------------------------------------------------

def small_section_is_one_chunk():
    chunks = text.chunks_for_document(short_section(), META)
    assert len(chunks) == 1, len(chunks)
    assert len(body(chunks[0])) <= text.CAP_CHARS


def long_section_respects_target_and_cap():
    chunks = text.chunks_for_document(long_section(), META)
    assert len(chunks) > 1, "a long section must not become one giant chunk"
    sizes = [len(body(chunk)) for chunk in chunks]
    assert max(sizes) <= text.CAP_CHARS, max(sizes)
    # Greedy packing fills to the target before starting a new chunk.
    assert all(size > text.TARGET_CHARS // 2 for size in sizes[:-1]), sizes


def overlap_carries_whole_sentences():
    chunks = text.chunks_for_document(long_section(), META)
    previous = body(chunks[0]).strip().split(". ")[-1]
    nxt = body(chunks[1]).strip()
    assert previous[:40] in nxt, (previous[:60], nxt[:60])
    assert nxt[0].isupper(), "a chunk must not start mid-sentence"


def oversized_paragraph_splits_at_sentences():
    one = " ".join(["This sentence is here to fill the paragraph out."] * 60)
    pages = [Page(1, ["1. BACKGROUND", one])]
    chunks = text.chunks_for_document(pages, META)
    assert len(chunks) > 1, len(chunks)
    for chunk in chunks:
        assert len(body(chunk)) <= text.CAP_CHARS
        assert body(chunk).strip().endswith("."), body(chunk)[-40:]


# --- prefix --------------------------------------------------------------

def prefix_names_year_section_and_pages():
    chunks = text.chunks_for_document(short_section(), META)
    head = chunks[0].text.split("\n\n", 1)[0]
    assert head.startswith("1970 Banko Janakari, Vol. 15, No. 2"), head
    assert "journal-article" in head and "1. BACKGROUND" in head, head
    assert "| p1" in head, head


def prefix_skips_empty_fields():
    bare = DocMeta(file="x.pdf")
    chunks = text.chunks_for_document(short_section(), bare)
    head = chunks[0].text.split("\n\n", 1)[0]
    assert "None" not in head and "||" not in head, head
    assert "(no section headings)" not in head, head      # this doc has a heading


def headingless_prefix_says_so():
    pages = [Page(1, ["no heading, just prose about bamboo."])]
    chunks = text.chunks_for_document(pages, META)
    assert chunks[0].section_path == [] and chunks[0].section_path_source == "none"
    assert "(no section headings)" in chunks[0].text.split("\n\n", 1)[0]


# --- chunk ids and metadata ---------------------------------------------

def ids_are_unique_and_sequential():
    chunks = text.chunks_for_document(long_section(), META)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)
    assert [chunk.chunk_id.rsplit(":", 1)[1] for chunk in chunks] == [
        f"{index:04d}" for index in range(len(chunks))]


def page_range_never_inverted():
    for chunk in text.chunks_for_document(long_section(), META):
        assert chunk.page_start <= chunk.page_end, chunk.chunk_id


# --- no chunk crosses a heading -----------------------------------------

def _corpus() -> dict[str, list]:
    docs: dict[str, list] = {}
    for line in PARSED.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        docs.setdefault(record["doc"], []).append(
            Page(record["pdf_page"], record["blocks"], record["text"]))
    for pages in docs.values():
        pages.sort(key=lambda page: page.pdf_page)
    return docs


def real_corpus_chunks_stay_in_one_section():
    docs = _corpus()
    for doc, pages in docs.items():
        sections = structure.split_sections(pages)
        blocks = {block.index: block for block in structure.document_blocks(pages)}
        chunks = text.chunks_for_document(pages, DocMeta(file=doc))
        assert chunks, f"{doc}: no chunks"
        for chunk in chunks:
            assert chunk.block_indices, f"{doc}: chunk with no source blocks"
            structure.assert_no_cross_section(
                [blocks[index] for index in chunk.block_indices], sections)
            assert len(body(chunk)) <= text.CAP_CHARS, (
                f"{doc} {chunk.chunk_id}: body {len(body(chunk))} over the cap")


def real_corpus_sections_do_not_mix():
    """The first chunk of a section never carries the previous section's text."""
    marahatta = [pages for doc, pages in _corpus().items()
                 if doc.startswith("1970_Marahatta")]
    assert marahatta, "no Marahatta document in the parsed corpus"
    pages = marahatta[0]
    sections = structure.split_sections(pages)
    chunks = text.chunks_for_document(pages, DocMeta(file="m.pdf"))
    firsts = {}
    for chunk in chunks:
        firsts.setdefault(tuple(chunk.section_path), chunk)
    assert len(firsts) == len({tuple(section.path) for section in sections}), (
        f"{len(firsts)} first chunks for {len(sections)} sections")


def main() -> int:
    print("size and overlap")
    for name, fn in [("a short section is one chunk", small_section_is_one_chunk),
                     ("a long section respects target and cap", long_section_respects_target_and_cap),
                     ("overlap carries whole sentences", overlap_carries_whole_sentences),
                     ("an oversized paragraph splits at sentences", oversized_paragraph_splits_at_sentences)]:
        check(name, fn)

    print("prefix")
    for name, fn in [("prefix names year, section and pages", prefix_names_year_section_and_pages),
                     ("prefix skips empty fields", prefix_skips_empty_fields),
                     ("headingless document says so in the prefix", headingless_prefix_says_so)]:
        check(name, fn)

    print("ids and metadata")
    for name, fn in [("chunk ids are unique and sequential", ids_are_unique_and_sequential),
                     ("page range is never inverted", page_range_never_inverted)]:
        check(name, fn)

    print("no chunk crosses a heading (real corpus)")
    for name, fn in [("every chunk's blocks come from one section",
                      real_corpus_chunks_stay_in_one_section),
                     ("sections do not share a first chunk", real_corpus_sections_do_not_mix)]:
        check(name, fn)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
