"""Table-route retrieval: the pages whose cleaned table text matches the question.

The table route already asks for figures, but page BM25 scores a page's *running text*,
while the table's rows are stored cell by cell in `index/chunks.jsonl` (268 table
chunks). A question like "In Table 2, how many Midhills households do not believe ..."
therefore misses the page whose table holds the row, and the model is handed prose that
reads around the answer instead of the row itself.

This module scores those table chunks with the same `corpus.BM25` class the page list
uses, maps the hits back to the page each chunk came from, and merges up to `SLOTS` of
them into the route's passages **without changing the total** — the route's prompt budget
is unchanged, so the only thing that moves is which pages the model reads.

It is behind a flag (`CHAT_TABLE_RETRIEVAL=1`) until a measured run says keep it
(Step 9, D-069). With the flag off, `merge()` returns its input untouched, so the
baseline is exactly the pipeline the eval already accepted.

Usage:
    from corpus import build, search
    from retrieval import tables

    index = build()
    hits = search(index, question, k=6)
    if tables.enabled():
        hits = tables.merge(index, question, hits, k=6)

Example (a table question that page BM25 misses):
    >>> hits = search(index, "In Table 2, how many Midhills households do not believe?", k=6)
    >>> merged = tables.merge(index, "In Table 2, how many Midhills households do not believe?", hits, k=6)
    >>> merged[-1]["via"]
    'table'
"""

from __future__ import annotations

import json
import os
import pathlib

from corpus import BM25, ROOT, context_for, snippet, tokens

CHUNKS = ROOT / "index" / "chunks.jsonl"
FLAG = "CHAT_TABLE_RETRIEVAL"
SLOTS = 2          # pages a table pass may take from the tail of the route's list

# D-073: the second table experiment. The first one (D-070) changed *which* pages the
# model reads and changed nothing, because the page was already rank 1. This one changes
# what the model sees of a page it already has: the cleaned rows of the table on it,
# which is the text a table question has to quote (q047's gold quote is a row).
CONTENT_FLAG = "CHAT_TABLE_CONTENT"
ROWS_CHARS = 900   # characters of one page's table text a passage may add

_CACHE: dict[str, tuple[int, list[dict], BM25 | None]] = {}


def enabled() -> bool:
    """Is the table pass switched on for this process?

    Read from the environment on every call rather than captured at import, so a test or
    a measurement can flip it without a fresh interpreter.
    """
    return os.environ.get(FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def table_chunks(path: pathlib.Path = CHUNKS) -> list[dict]:
    """Every chunk whose type is `table`, in index order."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("type") == "table" and (row.get("text") or "").strip():
            rows.append(row)
    return rows


def _reader(path: pathlib.Path) -> tuple[list[dict], BM25 | None]:
    """The table chunks and their BM25, rebuilt when the chunk file changes."""
    stamp = path.stat().st_mtime_ns if path.exists() else 0
    cached = _CACHE.get(str(path))
    if cached is not None and cached[0] == stamp:
        return cached[1], cached[2]
    chunks = table_chunks(path)
    reader = BM25([{"text": chunk["text"]} for chunk in chunks]) if chunks else None
    _CACHE[str(path)] = (stamp, chunks, reader)
    return chunks, reader


def _page_hit(page: dict, score: float, terms: list[str]) -> dict:
    """A page record shaped exactly like `corpus.search`'s, so nothing downstream branches."""
    return {
        "doc": page["doc"],
        "page": page["page"],
        "label": page["label"],
        "ocr": page.get("source") == "ocr",
        "score": round(score, 3),
        "context": context_for(page["text"], terms),
        "snippet": snippet(page["text"], terms),
        "via": "table",
    }


def rows_enabled() -> bool:
    """Is the table-content pass switched on for this process? (Separate flag, D-073.)"""
    return os.environ.get(CONTENT_FLAG, "").strip().lower() in ("1", "true", "yes", "on")


def rows_by_page(path: pathlib.Path = CHUNKS) -> dict[tuple[str, int], str]:
    """The table text indexed under each page, joined when a page holds several tables."""
    pages: dict[tuple[str, int], list[str]] = {}
    for chunk in table_chunks(path):
        key = (chunk["file"], int(chunk["page_start"]))
        pages.setdefault(key, []).append(chunk["text"].strip())
    return {key: "\n".join(texts) for key, texts in pages.items()}


def with_rows(hits: list[dict], *, rows: dict[tuple[str, int], str] | None = None,
              limit: int = ROWS_CHARS) -> list[dict]:
    """Append each hit page's own table rows to its passage body, in place-safe copies.

    A page keeps its heading and its prose window; the rows are added after them, so the
    model can quote a row exactly as the page holds it. A page with no table is returned
    unchanged, and so is every hit when the flag is off.

    Usage (the D-073 experiment; off unless CHAT_TABLE_CONTENT=1):
        >>> tables.with_rows(search(index, q, k=6))[0]["context"].count("TABLE ROWS")
        1
    """
    if not rows_enabled():
        return hits
    lookup = rows if rows is not None else rows_by_page()
    if not lookup:
        return hits
    out = []
    for hit in hits:
        text = lookup.get((hit.get("doc"), hit.get("page")))
        if not text:
            out.append(hit)
            continue
        body = (hit.get("context") or hit.get("text") or "").rstrip()
        out.append({**hit, "context": (f"{body}\n\nTABLE ROWS FROM THIS PAGE "
                                      f"(quoted from the page, one row per line):\n"
                                      f"{text[:limit]}")})
    return out


def merge(index: dict, query: str, hits: list[dict], *, k: int, slots: int = SLOTS,
          path: pathlib.Path = CHUNKS) -> list[dict]:
    """Add up to `slots` table-evidence pages to `hits`, keeping the list at most `k` long.

    The table pages replace the weakest page hits rather than being appended, because the
    route's `k` is a prompt-budget decision (6 passages on a 4096-token context). A page
    already in `hits` is never added twice, and a page with no indexed text is skipped
    (there is nothing to quote from it).
    """
    terms = tokens(query)
    if not terms or slots <= 0 or not hits:
        return hits
    if not os.environ.get(FLAG, "").strip().lower() in ("1", "true", "yes", "on"):
        return hits

    chunks, reader = _reader(path)
    if not chunks or reader is None:
        return hits

    present = {(hit["doc"], hit["page"]) for hit in hits}
    by_page = {(page["doc"], page["page"]): page for page in index["pages"]}
    added: list[dict] = []
    for score, position in sorted(((reader.score(terms, i), i) for i in range(len(chunks))),
                                  reverse=True):
        if score <= 0:
            break
        chunk = chunks[position]
        key = (chunk["file"], int(chunk["page_start"]))
        if key in present:
            continue
        page = by_page.get(key)
        if page is None or not page.get("text"):
            continue
        present.add(key)
        added.append(_page_hit(page, score, terms))
        if len(added) >= slots:
            break

    if not added:
        return hits

    keep = max(min(len(hits), 1), k - len(added))
    merged = list(hits[:keep])
    seen = {(hit["doc"], hit["page"]) for hit in merged}
    merged.extend(hit for hit in added if (hit["doc"], hit["page"]) not in seen)
    return merged
