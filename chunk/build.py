"""Assemble a document's chunks: text and tables, once each, in reading order.

This is the only place that knows both chunkers exist. It runs tables first,
because their bboxes decide which blocks the text chunker must skip — that is
what stops a table being embedded twice, once as prose and once as a table.

Table chunks get their section path from the section their blocks fall in, so a
table on page 6 still says which section it belongs to.

Usage:
    from chunk.base import DocMeta
    from chunk.build import chunks_for_document
    chunks = chunks_for_document(pages, DocMeta(file="1970_Das_....pdf", year=1970))
    [(c.type, c.section_path[-1:] , c.page_start) for c in chunks][:3]
"""

from __future__ import annotations

from chunk import structure, tables, text
from chunk.base import Chunk, DocMeta


def chunks_for_document(pages, meta: DocMeta) -> list[Chunk]:
    """Every chunk of one document, renumbered in reading order."""
    sections = structure.split_sections(pages)
    lookup = structure.section_lookup(sections)

    table_chunks, skip = tables.chunks_for_document(pages, meta)
    for chunk in table_chunks:
        positions = {lookup[index] for index in chunk.block_indices if index in lookup}
        if len(positions) == 1:
            section = sections[positions.pop()]
            chunk.section_path = list(section.path)
            chunk.section_path_source = section.source
        else:
            # A table outside any section (OCR page, headingless document) keeps an
            # empty path and says so, rather than borrowing a neighbour's.
            chunk.section_path_source = "none"

    text_chunks = text.chunks_for_document(pages, meta, skip=skip)
    merged = text_chunks + table_chunks
    merged.sort(key=lambda chunk: (chunk.page_start,
                                   0 if chunk.type == "text" else 1,
                                   chunk.chunk_id))
    for position, chunk in enumerate(merged):
        chunk.chunk_id = (f"{_stem(meta.file)}:p{chunk.page_start}-{chunk.page_end}:"
                          f"{position:04d}")
    return merged


def _stem(file: str) -> str:
    return file[:-4] if file.lower().endswith(".pdf") else file
