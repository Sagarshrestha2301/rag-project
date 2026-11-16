"""The page corpus: one owner for page text, page words, and the page -> file path.

Every module that needs to know what a corpus page says asks this module. Before, four
places did their own lookup: `ui/retrieval.py` built a page index, `generation/verify.py`
opened PDFs and fell back to that index, `ingest/verify.py` opened PDFs for words, and
`generation/cache.py` hashed bare file names. They disagreed about paths (a bare name vs
a corpus-relative path) and each kept a private cache. Now there is one path rule and one
page-text rule, and the callers say what they need: a page's text, its words, or a
fingerprint that changes when the page does.

The page index is a cache, not the authority. `page_text()` reads the PDF first, because a
quotation has to be on the page the reader will open; only a page with no text layer falls
back to the OCR text stored in `index/pages.json`. `page_fingerprint()` never reads the
index: it hashes the page text, or the whole file for a scan, so the answer cache can
notice a page that was removed or edited after the answer was stored.

Usage:
    from corpus import build, page_text, page_words, path_for, search
    index = build()
    hits = search(index, "24-hour rainfall at Tistung", k=4)
    page_text(hits[0]["doc"], hits[0]["page"])      # the PDF page, OCR fallback
    page_words(hits[0]["doc"], hits[0]["page"])     # the page's own word list
    path_for(hits[0]["doc"])                       # data/corpus/<file>.pdf

Output:
    index/pages.json                                 (gitignored, rebuilds on a corpus change)
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re

import pymupdf

CORPUS = pathlib.Path("data/corpus")
INDEX_CACHE = pathlib.Path("index/pages.json")
MIN_PAGE_CHARS = 40          # shorter than this means no text layer -> try OCR
OCR_DPI = 200                # render resolution for OCR; 150 is pymupdf4llm's default
MAX_PAGE_CHARS = 6000        # keep the cached index small; matches Step 1 practice
HEAD_CHARS = 700             # page opening, so the model sees what the page is
WINDOW_CHARS = 1200          # the passage where the question's terms actually appear


def files(root: pathlib.Path = CORPUS) -> list[pathlib.Path]:
    """Every corpus PDF, recursively: new documents keep their source folder.

    D-030 mirrors `data/raw`'s relative folders inside `data/corpus`, so a flat glob
    would silently ignore everything the Drive sample added. A duplicate file name is a
    corpus mistake, not something to paper over: pages and citations identify a document
    by name, so two names that collide cannot be told apart downstream.
    """
    found = sorted(root.rglob("*.pdf"))
    seen: dict[str, pathlib.Path] = {}
    for path in found:
        if path.name in seen:
            raise RuntimeError(
                f"duplicate corpus file name {path.name!r}: {seen[path.name]} and {path}")
        seen[path.name] = path
    return found


def path_for(doc: str, root: pathlib.Path = CORPUS) -> pathlib.Path:
    """The file behind a name (bare) or a corpus-relative path recorded in a page record."""
    wanted = str(doc).replace("\\", "/")
    direct = root / pathlib.PurePosixPath(wanted)
    if direct.is_file():
        return direct

    name = pathlib.PurePosixPath(wanted).name
    matches = [path for path in root.rglob(name) if path.name == name]
    if not matches:
        raise FileNotFoundError(f"no corpus file named {doc!r} under {root}")
    if len(matches) > 1:
        raise RuntimeError(f"corpus file name {doc!r} is ambiguous: {[str(m) for m in matches]}")
    return matches[0]


def signature(root: pathlib.Path = CORPUS) -> list[dict]:
    """Name, size and mtime of every corpus PDF.

    Stored in the page index so a changed or replaced document rebuilds it instead of
    silently searching the old text. The answer cache uses the same fact as its index
    version, so a corpus edit is a miss there too.
    """
    return [{"doc": path.name, "size": path.stat().st_size, "mtime": path.stat().st_mtime_ns}
            for path in files(root)]


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def label_for(filename: str) -> str:
    """'1970_Das_Beliefs_..._W1999918290.pdf' -> 'Das 1970'."""
    match = re.match(r"^(\d{4}|0)_([A-Za-z]+)", filename)
    if match:
        year, author = match.group(1), match.group(2)
        return author if year in ("0", "") else f"{author} {year}"
    return filename[:24]


def ocr_document(pdf: pathlib.Path) -> dict[int, str]:
    """OCR a PDF with the pinned parser; {page_number(1-based): text}.

    Only called for documents that contain at least one page without a text layer, so
    ordinary PDFs never pay the ~5 s/page OCR cost.
    """
    import pymupdf4llm  # imported lazily: pulls in RapidOCR and its ONNX models

    try:
        chunks = pymupdf4llm.to_markdown(
            str(pdf), page_chunks=True, use_ocr=True, ocr_dpi=OCR_DPI
        )
    except Exception as exc:  # noqa: BLE001 - a failed OCR must not kill the index
        print(f"[corpus] OCR failed for {pdf.name}: {exc.__class__.__name__}: {exc}")
        return {}

    out: dict[int, str] = {}
    for position, chunk in enumerate(chunks):
        # pymupdf4llm 2.1 returns one chunk per page in page order but leaves
        # `metadata["page"]` unset, so the position is the page number.
        page = (chunk.get("metadata") or {}).get("page")
        number = (int(page) + 1) if page is not None else position + 1
        text = re.sub(r"[|#*_`]+", " ", chunk.get("text") or "")
        out[number] = re.sub(r"\s+", " ", text).strip()
    return out


def build(force: bool = False, root: pathlib.Path = CORPUS,
          cache: pathlib.Path = INDEX_CACHE) -> dict:
    """Read every corpus PDF and return {pages, unreadable, docs, signature}.

    Pages without a text layer are OCR'd, so a scanned paper becomes searchable and
    citable instead of reporting an empty page.
    """
    fingerprint = signature(root)
    if cache.exists() and not force:
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("pages") and cached.get("signature") == fingerprint:
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    pages: list[dict] = []
    unreadable: dict[str, list[int]] = {}
    docs: list[dict] = []
    ocr_pages = 0

    for pdf in files(root):
        bad: list[int] = []
        with pymupdf.open(pdf) as doc:
            texts = [re.sub(r"\s+", " ", page.get_text()).strip() for page in doc]
            page_count = doc.page_count

        ocr_text: dict[int, str] = {}
        if any(len(t) < MIN_PAGE_CHARS for t in texts):
            ocr_text = ocr_document(pdf)

        for number, text in enumerate(texts, start=1):
            source = "text"
            if len(text) < MIN_PAGE_CHARS and ocr_text.get(number):
                text, source = ocr_text[number], "ocr"
                ocr_pages += 1
            if len(text) < MIN_PAGE_CHARS:
                bad.append(number)
            pages.append({
                "doc": pdf.name,
                "page": number,
                "label": label_for(pdf.name),
                "text": text[:MAX_PAGE_CHARS],
                "source": source,
            })
        docs.append({"doc": pdf.name, "label": label_for(pdf.name), "pages": page_count})
        if bad:
            unreadable[pdf.name] = bad

    index = {"pages": pages, "unreadable": unreadable, "docs": docs,
             "signature": fingerprint, "ocr_pages": ocr_pages}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(index), encoding="utf-8")
    return index


def _raw_page_text(path: pathlib.Path, page: int) -> str | None:
    """The PDF's own text for one page; None when the file or page does not exist."""
    try:
        with pymupdf.open(path) as pdf:
            if not 1 <= page <= pdf.page_count:
                return None
            return pdf[page - 1].get_text()
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not crash a check
        print(f"[corpus] cannot read {path.name} p{page}: {exc.__class__.__name__}: {exc}")
        return None


def _indexed_text(doc: str, page: int, cache: pathlib.Path = INDEX_CACHE) -> str:
    """The OCR text the index stored for a scanned page, if it has one."""
    if not cache.exists():
        return ""
    try:
        pages = json.loads(cache.read_text(encoding="utf-8")).get("pages", [])
    except (json.JSONDecodeError, OSError):
        return ""
    name = pathlib.PurePosixPath(str(doc).replace("\\", "/")).name
    for entry in pages:
        if entry.get("doc") == name and entry.get("page") == page:
            return entry.get("text") or ""
    return ""


def page_text(doc: str, page: int, root: pathlib.Path = CORPUS,
              cache: pathlib.Path = INDEX_CACHE) -> str:
    """One page's text from the PDF, with the indexed OCR text as fallback.

    The PDF is the authority, because a quotation has to be on the page the reader will
    open. A scanned page has no text layer, so the OCR text the index built is the only
    text there is to quote; that is what the retriever showed the model in the first
    place.
    """
    try:
        path = path_for(doc, root)
    except (FileNotFoundError, RuntimeError):
        return ""

    text = _raw_page_text(path, page)
    if text is None:
        return ""
    if len(re.sub(r"\s+", "", text)) < MIN_PAGE_CHARS:
        text = _indexed_text(doc, page, cache) or text
    return text


def page_words(doc: str, page: int, root: pathlib.Path = CORPUS) -> set[str]:
    """The page's own word list, for checks that compare a cell with printed words."""
    try:
        path = path_for(doc, root)
    except (FileNotFoundError, RuntimeError):
        return set()
    try:
        with pymupdf.open(path) as pdf:
            if not 1 <= page <= pdf.page_count:
                return set()
            return {word[4] for word in pdf[page - 1].get_text("words")}
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not crash a check
        print(f"[corpus] cannot read {path.name} p{page}: {exc.__class__.__name__}: {exc}")
        return set()


def page_fingerprint(doc: str, page: int, root: pathlib.Path = CORPUS) -> str:
    """A value that changes when this page is removed or edited; "" when unreadable.

    The answer cache stores one per cited page. A text page is fingerprinted by its text,
    so a re-saved PDF with the same words still verifies. A page with no text layer is
    fingerprinted by the whole file instead: the OCR text in the index could otherwise
    outlive a changed scan and make a stale answer look current.
    """
    try:
        path = path_for(doc, root)
    except (FileNotFoundError, RuntimeError):
        return ""

    text = _raw_page_text(path, page)
    if text is None:
        return ""
    if len(re.sub(r"\s+", "", text)) >= MIN_PAGE_CHARS:
        return "text:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        return "file:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


class BM25:
    """Small BM25. k1/b are the usual defaults; the corpus is tiny.

    Public because `retrieval/hybrid.py` scores chunks with the same class: one scorer,
    two granularities, so a hybrid comparison cannot drift from the page baseline it is
    measured against.
    """

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
_CACHE_BM25: BM25 | None = None


def _bm25(index: dict) -> BM25:
    global _CACHE_KEY, _CACHE_BM25
    key = (id(index), len(index["pages"]))
    if _CACHE_BM25 is None or _CACHE_KEY != key:
        # Build over every page, readable or not, so BM25 indices match the page list.
        # Filtering here would shift every index and score the wrong page.
        _CACHE_BM25 = BM25(index["pages"])
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

    Truncating to the page head loses answers that sit mid-page (q001's 540 mm is ~2000
    characters into Marahatta p2), which makes a correct retrieval look like a miss to
    the model.
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
            "ocr": page.get("source") == "ocr",
            "score": round(score, 3),
            "context": context_for(page["text"], terms),
            "snippet": snippet(page["text"], terms),
        })
    return hits
