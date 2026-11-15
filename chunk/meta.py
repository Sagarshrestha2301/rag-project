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

# Page-1 evidence, used only when the file name or folder says nothing. Measured on
# this corpus: 33 of 97 documents have no year in the name and 59 have no publisher
# folder. Reading the page recovers a few of them and invents nothing, because the
# value taken is the text that is printed there.
#
# Deliberately NOT used: a bare "March 2020" anywhere on page 1. That matched six
# documents, two of them with "April 2026" in a footer, and a footer date is the
# print date, not the publication year. Only a volume line or a copyright line is
# treated as publication metadata.
VOLUME_YEAR = re.compile(r"(?i)\b(?:vol\.?|volume)\s*\d+[^\n]{0,60}?\b(?P<year>(?:19|20)\d{2})\b")
COPYRIGHT_YEAR = re.compile(r"(?i)(?:©|copyright|\(c\))\s*(?P<year>(?:19|20)\d{2})")
# An outlet name is taken verbatim from the page and cut at the volume marker, so
# `Journal of Hydrology and Meteorology, Vol. 5` becomes `Journal of Hydrology and Meteorology`.
OUTLET = re.compile(
    r"\b((?:[A-Z][A-Za-z&'\-]*\s+){0,3}(?:Journal|Bulletin|Proceedings|Transactions|Newsletter|Magazine)"
    r"(?:\s+of\s+(?:(?:(?!Vol\b|Volume\b|No\b|Issue\b)[A-Z][A-Za-z&,'\-]*|and|for|in)\s*){1,8})?)"
    r"(?=\s*[,.;:]|\s+(?:Vol|Volume|No|Issue)\b|$)")


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


# How much of page 1 counts as the masthead. Beyond this a match is usually a
# citation: `Journal of Hydrology and Meteorology, Vol. 7` sits in the references
# on page 1 of two papers, and taking it as their publisher would be wrong.
HEAD_CHARS = 300
MONTH_YEAR = re.compile(
    r'(?i)\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+((?:19|20)\d{2})\b')


def year_from_text(text: str) -> int | None:
    """The publication year a page prints in a volume line or a copyright line.

    Volume first: `Vol. 5, No. 1, 2019` names the publication year, then a
    copyright line, then a month and year in the masthead. All three are read from
    the top of page 1 only, because further down they belong to citations: two
    papers on page 1 cite `Journal of Hydrology and Meteorology, Vol. 7, 2010`.
    """
    head = (text or "")[:HEAD_CHARS]
    for pattern in (VOLUME_YEAR, COPYRIGHT_YEAR):
        match = pattern.search(head)
        if match:
            year = int(match.group("year"))
            if 1900 <= year <= 2100:
                return year
    match = MONTH_YEAR.search(head)
    return int(match.group(1)) if match else None


def publisher_from_text(text: str) -> str:
    """A journal or bulletin name printed on the page, trimmed, or "".

    Never derived from a topic folder (`01_Floods_GLOFs` is not a publisher) and
    never invented: the returned string occurs in the page text as written.
    """
    match = OUTLET.search((text or "")[:HEAD_CHARS])
    if not match:
        return ""
    # The name may swallow the comma before `Vol.`; a trailing punctuation mark is
    # part of the sentence, not part of the journal's name.
    name = " ".join(match.group(1).split()).strip(" ,;.")
    if len(name) < 6 or any(character.isdigit() for character in name):
        return ""
    return name


def apply(chunks, meta: DocMeta) -> list:
    """Copy the document metadata onto every chunk of that document."""
    for chunk in chunks:
        chunk.year = meta.year
        chunk.publisher = meta.publisher
        chunk.doc_type = meta.doc_type
        chunk.doc_context = meta.doc_context
    return chunks
