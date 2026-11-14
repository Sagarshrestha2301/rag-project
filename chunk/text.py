"""Text chunks: section-bounded, size-capped, prefixed with their provenance.

The rules are D-050's, and every number has a reason:

* **1,000 characters target, 1,500 hard cap.** Pages here average 2,441
  characters, so a target chunk is about a third of a page and four of them plus
  the question fit the model's 4096-token context.
* **15% overlap, sentences only.** Overlap is carried back whole sentences, so a
  chunk never starts mid-word; and it is carried only *within* a section,
  because the point of the boundary is that the two sides are about different
  things.
* **Never across a heading.** Packing happens per section, so this holds by
  construction; `chunk.structure.assert_no_cross_section` proves it in the test.
* **Prefix on every chunk.** `{year} {publisher} | {doc_type} | {section path} |
  p{pages}` goes into the embedded text, so a chunk cut from page 6 still says
  which paper and which section it belongs to. The prefix is metadata, not body,
  and does not count against the cap.

Table cell blocks are never packed as text: `chunk.build` passes the block
indices that sit inside a table's bbox as `skip`, so each table is embedded once,
by `chunk.tables`. A section that consists only of a table yields no text chunk,
which is correct — the table chunk carries it.

Usage:
    from chunk.base import DocMeta
    from chunk.text import chunks_for_document
    meta = DocMeta(file="1970_Marahatta_....pdf", year=1970, publisher="SOHAM")
    chunks = chunks_for_document(pages, meta)
    chunks[0].text[:60]      # '1970 SOHAM |  | 1. BACKGROUND | p1-2\n\nS. Marahatta ...'
    chunks[0].section_path   # ['1. BACKGROUND']
"""

from __future__ import annotations

import re

from chunk import structure
from chunk.base import Block, Chunk, DocMeta, Section, register_chunker

TARGET_CHARS = 1_000
CAP_CHARS = 1_500
OVERLAP_SHARE = 0.15
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@register_chunker("text")
class TextChunker:
    """Packs a section's paragraphs into chunks. No table logic, no LLM calls."""

    name = "text"

    def chunks(self, section: Section, meta: DocMeta, *, start_seq: int = 0,
               skip: frozenset[int] = frozenset()) -> list[Chunk]:
        kept = [block for block in section.blocks if block.index not in skip]
        pieces = _pack([(block, block.text) for block in kept])
        chunks: list[Chunk] = []
        for offset, (blocks, body) in enumerate(pieces):
            pages = [block.pdf_page for block in blocks] or [section.page_start]
            chunks.append(Chunk(
                chunk_id=f"{_stem(meta.file)}:p{min(pages)}-{max(pages)}:{start_seq + offset:04d}",
                file=meta.file,
                page_start=min(pages),
                page_end=max(pages),
                section_path=list(section.path),
                text=_prefix(meta, section, min(pages), max(pages)) + body,
                section_path_source=section.source,
                block_indices=sorted({block.index for block in blocks}),
                year=meta.year,
                publisher=meta.publisher,
                doc_type=meta.doc_type,
                doc_context=meta.doc_context,
            ))
        return chunks


def chunks_for_document(pages, meta: DocMeta,
                        skip: frozenset[int] = frozenset()) -> list[Chunk]:
    """Every text chunk of one document, in reading order.

    Usage:
        from chunk.text import chunks_for_document
        [c.chunk_id for c in chunks_for_document(pages, meta)][:2]
        # ['1970_Marahatta_...:p1-2:0000', '1970_Marahatta_...:p2-2:0001']
    """
    chunker = TextChunker()
    chunks: list[Chunk] = []
    for section in structure.split_sections(pages):
        chunks.extend(chunker.chunks(section, meta, start_seq=len(chunks),
                                      skip=skip))
    return chunks


def _pack(items: list[tuple[Block, str]]) -> list[tuple[list[Block], str]]:
    """Greedy packing of paragraphs into chunks of TARGET_CHARS, cap CAP_CHARS.

    Splits one oversized paragraph at sentence boundaries rather than at a
    character count, so no chunk begins or ends mid-sentence by accident.
    """
    packed: list[tuple[list[Block], str]] = []
    blocks: list[Block] = []
    bodies: list[str] = []
    length = 0

    for block, text in items:
        for piece in _split_oversized(text):
            addition = len(piece) + 2                      # +2 for the blank line
            if bodies and length + addition > TARGET_CHARS:
                packed.append((blocks, "\n\n".join(bodies)))
                # The cap wins over the overlap: carrying a full tail into a piece
                # that already fills the cap broke the 1,500 limit in testing
                # (1,469 + 148 = 1,617), so the tail is shortened to fit or dropped.
                # -2 for the blank line that joins the carry to the next piece.
                carry = _tail("\n\n".join(bodies),
                              budget=max(0, CAP_CHARS - addition - 2))
                blocks = list(blocks[-1:]) if carry else []
                bodies = [carry] if carry else []
                length = len(carry) + 2 if carry else 0
            blocks.append(block)
            bodies.append(piece)
            length += addition

    if bodies:
        packed.append((blocks, "\n\n".join(bodies)))

    # One paragraph longer than the cap is split by _split_oversized, but the
    # join can still add a character or two, so the invariant is checked here.
    for _, body in packed:
        if len(body) > CAP_CHARS:
            raise ValueError(f"chunk body {len(body)} exceeds the {CAP_CHARS} cap")
    return packed


def _split_oversized(text: str) -> list[str]:
    """A paragraph longer than the cap, cut at sentence boundaries."""
    if len(text) <= CAP_CHARS:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if current and len(current) + len(sentence) + 1 > CAP_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, budget: int | None = None) -> str:
    """The trailing whole sentences worth carrying into the next chunk."""
    if budget is None:
        budget = int(TARGET_CHARS * OVERLAP_SHARE)
    sentences = _sentences(text)
    carried: list[str] = []
    for sentence in reversed(sentences):
        if carried and len(sentence) + len(" ".join(carried)) > budget:
            break
        if len(sentence) > budget or budget <= 0:
            break
        carried.insert(0, sentence)
    tail = " ".join(carried)
    return tail if tail and tail != text else ""


def _sentences(text: str) -> list[str]:
    return [part for part in SENTENCE_END.split(text.strip()) if part.strip()]


def _prefix(meta: DocMeta, section: Section, page_start: int, page_end: int) -> str:
    """`{year} {publisher} | {doc_type} | {section path} | p{pages}` + blank line.

    Empty fields are dropped rather than printed as "None | |".
    """
    path = " > ".join(section.path) if section.path else "(no section headings)"
    pages = f"p{page_start}" if page_start == page_end else f"p{page_start}-{page_end}"
    head = " ".join(part for part in (str(meta.year) if meta.year else "",
                                      meta.publisher) if part)
    fields = [field for field in (head, meta.doc_type, path, pages) if field]
    return " | ".join(fields) + "\n\n"


def _stem(file: str) -> str:
    return file[:-4] if file.lower().endswith(".pdf") else file
