"""Programmatic document metadata: year, publisher, document type (Step 4 task 3).

The corpus file names and folders carry what can be known without guessing:
`1970_Ahasan_..._W2100745337.pdf` starts with its year, `papers/<topic>/` holds
journal articles, and `reports/<organisation>/` names the publisher in the
folder. Nothing else is inferred — a missing publisher stays empty rather than
borrowing the topic folder name, because "01_Floods_GLOFs" is not a publisher.

The optional 2-line `doc_context` is generated separately (`chunk.doc_context`)
and merged in; this module never calls a model.

Usage:
    from chunk.meta import to_meta
    to_meta("data/corpus/reports/USGS/1991_..._18253.pdf")
    # DocMeta(file="1991_..._18253.pdf", year=1991, publisher="USGS", doc_type="report")
"""

from __future__ import annotations

import pathlib
import re

from chunk.base import DocMeta

YEAR = re.compile(r"^(?P<year>(?:19|20)\d{2})_")
DOC_TYPE_BY_FOLDER = {"papers": "journal-article", "reports": "report"}
PUBLISHER_FOLDER = "reports"      # only this folder type names an organisation


def path_parts(path: str | pathlib.Path) -> tuple[str, ...]:
    """The parts below `data/corpus`, so a bare name and a full path agree."""
    parts = pathlib.PurePosixPath(str(path).replace("\\", "/")).parts
    if "corpus" in parts:
        parts = parts[parts.index("corpus") + 1:]
    return parts


def to_meta(path: str | pathlib.Path) -> DocMeta:
    """Derive what the path states outright; leave the rest empty."""
    parts = path_parts(path)
    if not parts:
        raise ValueError(f"no file name in {path!r}")
    name = parts[-1]
    folders = parts[:-1]

    match = YEAR.match(name)
    year = int(match.group("year")) if match else None

    doc_type = DOC_TYPE_BY_FOLDER.get(folders[0], "") if folders else ""
    publisher = folders[1] if folders and folders[0] == PUBLISHER_FOLDER and len(folders) > 1 else ""

    return DocMeta(file=name, year=year, publisher=publisher, doc_type=doc_type)


def apply(chunks, meta: DocMeta) -> list:
    """Copy the document metadata onto every chunk of that document."""
    for chunk in chunks:
        chunk.year = meta.year
        chunk.publisher = meta.publisher
        chunk.doc_type = meta.doc_type
        chunk.doc_context = meta.doc_context
    return chunks
