"""Page-level retrieval over `data/corpus/` (prototype for Steps 4-5).

Pages, not chunks: chunking is decided in Step 4, and page-level retrieval keeps
a citation pointing at a real PDF page. BM25 is written out here rather than
added as a dependency, because the whole index is 42 pages and a library would
be more code than the scorer.

The index is cached to `index/ui-pages.json` so a restart is instant. Delete that
file (or call build(force=True)) after changing the corpus.

Usage:
    from ui.retrieval import build, search
    index = build()
    hits = search(index, "24-hour rainfall at Tistung", k=4)
    # [{"doc": "...pdf", "page": 2, "label": "Marahatta 1970", "snippet": "..."}]
"""

from __future__ import annotations

import json
import math
import pathlib
import re

import pymupdf

CORPUS = pathlib.Path("data/corpus")
CACHE = pathlib.Path("index/ui-pages.json")
MIN_PAGE_CHARS = 40          # shorter than this counts as unreadable (no text layer)
MAX_PAGE_CHARS = 6000        # keep the cached index small; matches Step 1 practice
HEAD_CHARS = 700             # page opening, so the model sees what the page is
WINDOW_CHARS = 1200          # the passage where the question's terms actually appear


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def label_for(filename: str) -> str:
    """'1970_Das_Beliefs_..._W1999918290.pdf' -> 'Das 1970'."""
    match = re.match(r"^(\d{4}|0)_([A-Za-z]+)", filename)
    if match:
        year, author = match.group(1), match.group(2)
        return author if year in ("0", "") else f"{author} {year}"
    return filename[:24]


def build(force: bool = False) -> dict:
    """Read every corpus PDF and return {pages, unreadable, docs}."""
    if CACHE.exists() and not force:
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if cached.get("pages"):
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    pages: list[dict] = []
    unreadable: dict[str, list[int]] = {}
    docs: list[dict] = []

    for pdf in sorted(CORPUS.glob("*.pdf")):
        bad: list[int] = []
        with pymupdf.open(pdf) as doc:
            for number, page in enumerate(doc, start=1):
                text = re.sub(r"\s+", " ", page.get_text()).strip()
                if len(text) < MIN_PAGE_CHARS:
                    bad.append(number)
                pages.append({
                    "doc": pdf.name,
                    "page": number,
                    "label": label_for(pdf.name),
                    "text": text[:MAX_PAGE_CHARS],
                })
            docs.append({"doc": pdf.name, "label": label_for(pdf.name), "pages": doc.page_count})
        if bad:
            unreadable[pdf.name] = bad

    index = {"pages": pages, "unreadable": unreadable, "docs": docs}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(index), encoding="utf-8")
    return index


class _BM25:
    """Small BM25. k1/b are the usual defaults; the corpus is tiny."""

    def __init__(self, pages: list[dict], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [tokens(p["text"]) for p in pages]
        self.lengths = [len(d) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: dict[str, int] = {}
        for doc in self.docs:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.tf: list[dict[str, int]] = []
        for doc in self.docs:
            counts: dict[str, int] = {}
            for term in doc:
                counts[term] = counts.get(term, 0) + 1
            self.tf.append(counts)

    def score(self, query: list[str], i: int) -> float:
        total = 0.0
        norm = self.k1 * (1 - self.b + self.b * (self.lengths[i] / self.avg if self.avg else 0))
        for term in query:
            f = self.tf[i].get(term, 0)
            if not f:
                continue
            total += self.idf.get(term, 0.0) * (f * (self.k1 + 1)) / (f + norm or 1)
        return total


_CACHE_KEY: tuple | None = None
_CACHE_BM25: _BM25 | None = None


def _bm25(index: dict) -> _BM25:
    global _CACHE_KEY, _CACHE_BM25
    key = (id(index), len(index["pages"]))
    if _CACHE_BM25 is None or _CACHE_KEY != key:
        # Build over every page, readable or not, so BM25 indices match the page
        # list. Filtering here would shift every index and score the wrong page.
        _CACHE_BM25 = _BM25(index["pages"])
        _CACHE_KEY = key
    return _CACHE_BM25


def best_window(text: str, terms: list[str], width: int = WINDOW_CHARS) -> tuple[int, str]:
    """The window of `width` chars containing the most distinct query terms."""
    low = text.lower()
    positions = sorted({at for term in terms if (at := low.find(term)) >= 0})
    if not positions:
        return 0, text[:width]
    best_start, best_count = 0, -1
    for at in positions:
        start = max(0, at - 200)
        window = low[start:start + width]
        count = sum(1 for term in terms if term in window)
        if count > best_count:
            best_start, best_count = start, count
    return best_start, text[best_start:best_start + width]


def context_for(text: str, terms: list[str]) -> str:
    """Page opening plus the passage most likely to answer the question.

    Truncating to the page head loses answers that sit mid-page (q001's 540 mm
    is ~2000 characters into Marahatta p2), which makes a correct retrieval look
    like a miss to the model.
    """
    start, window = best_window(text, terms)
    if start <= HEAD_CHARS:
        return text[: max(HEAD_CHARS, start + WINDOW_CHARS)]
    return text[:HEAD_CHARS] + "\n…\n" + window


def snippet(text: str, query: list[str], width: int = 220) -> str:
    """A readable window around the first query term that appears."""
    low = text.lower()
    at = -1
    for term in query:
        found = low.find(term)
        if found >= 0 and (at < 0 or found < at):
            at = found
    if at < 0:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, at - width // 3)
    piece = text[start:start + width].strip()
    return ("…" if start else "") + piece + ("…" if start + width < len(text) else "")


def search(index: dict, query: str, k: int = 4) -> list[dict]:
    """Top-k pages for a question, best first, with prompt context and snippet."""
    terms = tokens(query)
    if not terms:
        return []
    reader = _bm25(index)
    usable = [i for i, p in enumerate(index["pages"]) if p["text"]]
    scores = sorted(((reader.score(terms, i), i) for i in usable), reverse=True)

    hits = []
    for score, i in scores[:k]:
        if score <= 0:
            continue
        page = index["pages"][i]
        hits.append({
            "doc": page["doc"],
            "page": page["page"],
            "label": page["label"],
            "score": round(score, 3),
            "context": context_for(page["text"], terms),
            "snippet": snippet(page["text"], terms),
        })
    return hits
