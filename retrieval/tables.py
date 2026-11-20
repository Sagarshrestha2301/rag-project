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
